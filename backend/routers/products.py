from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from psycopg.types.json import Json

from db import execute, fetch_all, fetch_one
from security import current_user, optional_user, require_manager
from audit import log_action, traffic_source
from media import save_image, make_thumb
from notifications import notify_users

router = APIRouter()

# Storefront sort options → SQL. Whitelisted (never interpolate a client string
# into an ORDER BY). "featured" is the manager-set display order.
SORT_SQL = {
    "featured": "sort, created_at",
    "newest": "created_at desc",
    "price_asc": "coalesce(sale_price, price), sort",
    "price_desc": "coalesce(sale_price, price) desc, sort",
    "name": "name",
}


def _clean_images(value):
    """Keep only non-empty string entries, preserving order."""
    if not isinstance(value, list):
        return []
    return [s for s in value if isinstance(s, str) and s.strip()]


def _blank_to_none(value):
    """Store an empty translation as NULL, not ''. The frontend falls back to the
    Arabic when the English is missing, and '' would defeat that check."""
    if value is None:
        return None
    return str(value).strip() or None


def _price(value):
    """Parse a price filter bound; None when absent or not a number."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _sale_price(value, price):
    """The offer price, checked against the price it's an offer on.

    None (or a cleared field) ends the offer. It has to be below the usual price, or
    the crossed-out price beside it on the shelf would be a lie — the one thing a
    shopper is entitled to trust about a sale.
    """
    if value in (None, ""):
        return None
    try:
        sale = round(float(value), 2)
    except (TypeError, ValueError):
        raise HTTPException(400, "The offer price must be a number")
    try:
        usual = float(price)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid price")
    if sale <= 0:
        raise HTTPException(400, "The offer price must be more than zero")
    if sale >= usual:
        raise HTTPException(400, "The offer price must be below the usual price")
    return sale


@router.get("")
def list_products(request: Request):
    user = optional_user(request)
    is_manager = user and user.get("role") == "manager"
    q = request.query_params
    force_active = q.get("active") == "1"   # storefront forces active-only even for managers
    category = q.get("category")
    ptype = (q.get("type") or "").strip()
    search = (q.get("q") or "").strip()

    conds, params = [], []
    if not is_manager or force_active:
        conds.append("is_active = true")
    if category in ("pantry", "pottery"):
        conds.append("category = %s")
        params.append(category)
    if ptype:
        conds.append("type = %s")
        params.append(ptype)
    if search:
        # Case-insensitive substring over both languages, so an English shopper
        # finds "olive oil" and an Arabic one finds "زيت زيتون" for the same product.
        conds.append("(name ilike %s or coalesce(name_en, '') ilike %s "
                     "or coalesce(description, '') ilike %s or coalesce(description_en, '') ilike %s)")
        params += [f"%{search}%"] * 4
    min_price, max_price = _price(q.get("min_price")), _price(q.get("max_price"))
    if min_price is not None:
        conds.append("coalesce(sale_price, price) >= %s")
        params.append(min_price)
    if max_price is not None:
        conds.append("coalesce(sale_price, price) <= %s")
        params.append(max_price)
    where = ("where " + " and ".join(conds)) if conds else ""
    order_by = SORT_SQL.get(q.get("sort") or "", SORT_SQL["featured"])
    # On the storefront, sold-out items sink to the end of whatever sort is active.
    # The manager inventory list keeps its configured order so stock can be managed.
    if not is_manager or force_active:
        order_by = "stock = 0, " + order_by

    # LIGHT payload: only a small thumbnail, never the heavy data-URL gallery
    # (the full images load on demand via GET /products/{id}).
    if is_manager and not force_active:
        cols = ("id, name, name_en, description, description_en, price, sale_price, unit, unit_en, "
                "category, type, tag, tag_en, "
                "coalesce(thumb_url, image_url) as image_url, thumb_url, stock, is_active, sort")
    else:
        cols = ("id, name, name_en, description, description_en, price, sale_price, unit, unit_en, "
                "category, type, tag, tag_en, "
                "coalesce(thumb_url, image_url) as image_url, stock, is_active, sort")

    # count(*) over () rides along on the same scan — window functions are applied
    # before LIMIT/OFFSET, so it's the full match count, not just this page. Saves
    # a second round-trip on the busiest endpoint in the app.
    sql = f"select {cols}, count(*) over ()::int as total_count from products {where} order by {order_by}"
    p2 = list(params)
    try:
        limit = int(q["limit"]) if q.get("limit") else None
    except ValueError:
        limit = None
    first_page = True
    if limit is not None:
        try:
            offset = max(0, int(q.get("offset", 0)))
        except ValueError:
            offset = 0
        sql += " limit %s offset %s"
        p2 += [limit, offset]
        first_page = offset == 0

    rows = fetch_all(sql, p2)
    total = rows[0]["total_count"] if rows else 0
    for r in rows:
        del r["total_count"]   # internal to the count-in-one-query trick above
    # "opened the storefront" signal — shoppers only, once per feed (first page).
    # The campaign tags on the landing URL ride along: it's the only place the shop
    # learns which ad or post actually brings shoppers in.
    if not is_manager and first_page:
        log_action(user_id=(user or {}).get("id"), action="visit",
                   detail={"ua": request.headers.get("user-agent"),
                           "from": traffic_source(request)}, request=request)
    return {"products": rows, "total": total}


@router.get("/types")
def list_types(request: Request):
    """Distinct sub-types in use, for the storefront filter chips. Active products
    only, ordered by how many products use each type (most common first).
    Defined before /{pid} so 'types' isn't captured as a product id."""
    q = request.query_params
    category = q.get("category")
    conds = ["is_active = true", "type is not null", "type <> ''"]
    params = []
    if category in ("pantry", "pottery"):
        conds.append("category = %s")
        params.append(category)
    where = "where " + " and ".join(conds)
    rows = fetch_all(
        f"select type, count(*)::int as n from products {where} group by type order by n desc, type",
        params,
    )
    return {"types": [r["type"] for r in rows]}


@router.get("/{pid}/related")
def related_products(pid: str):
    """Other products a shopper is likely to want next: same category, with the
    same sub-type ranked first, in-stock before sold-out. Light payload (thumb
    only) so it renders as a card row. Defined before /{pid} for route order."""
    rows = fetch_all(
        """with base as (
             select category, type from products where id = %s and is_active = true
           )
           select p.id, p.name, p.name_en, p.description, p.description_en, p.price, p.sale_price,
                  p.unit, p.unit_en, p.category, p.type, p.tag, p.tag_en,
                  coalesce(p.thumb_url, p.image_url) as image_url, p.stock, p.is_active, p.sort
           from products p, base b
           where p.is_active = true and p.id <> %s and p.category = b.category
           order by (p.type is not distinct from b.type) desc, p.stock = 0, p.sort, p.created_at
           limit 8""",
        [pid, pid],
    )
    return {"products": rows}


@router.post("/{pid}/stock-alert")
def add_stock_alert(pid: str, request: Request, user=Depends(current_user)):
    """"Tell me when it's back" — remembered until the product is restocked."""
    row = fetch_one("select id, name, stock from products where id = %s and is_active = true", [pid])
    if not row:
        raise HTTPException(404, "Product not found")
    if row["stock"] > 0:
        raise HTTPException(400, "This product is already in stock")
    execute(
        """insert into stock_alerts (user_id, product_id) values (%s, %s)
           on conflict (user_id, product_id) do nothing""",
        [user["id"], pid],
    )
    # A sale the shop lost for want of stock, with someone's name attached to it.
    # out_of_stock already records the basket that failed; this records the ones who
    # asked to be told, which is what makes a restock worth ordering.
    log_action(user_id=user["id"], action="stock_alert",
               detail={"product_id": pid, "name": row["name"]}, request=request)
    return {"subscribed": True}


@router.get("/{pid}/stock-alert")
def has_stock_alert(pid: str, user=Depends(current_user)):
    row = fetch_one("select 1 as x from stock_alerts where user_id = %s and product_id = %s", [user["id"], pid])
    return {"subscribed": bool(row)}


@router.get("/{pid}")
def get_product(pid: str, request: Request):
    user = optional_user(request)
    is_manager = user and user.get("role") == "manager"
    row = fetch_one(
        """select id, name, name_en, description, description_en, price, sale_price, unit, unit_en,
                  category, type, tag, tag_en, image_url, images, thumb_url, stock, is_active, sort
           from products where id = %s""", [pid])
    if not row or (not is_manager and not row["is_active"]):
        raise HTTPException(404, "Product not found")
    # "opened a product" signal — shoppers only. Records which product (id + name)
    # so the activity log can link straight to it and rank the most-opened items.
    if not is_manager:
        log_action(user_id=(user or {}).get("id"), action="product_view",
                   detail={"product_id": row["id"], "name": row["name"]}, request=request)
    return {"product": row}


@router.post("")
def create_product(response: Response, _m=Depends(require_manager), payload: dict = Body(default={})):
    name, price, category = payload.get("name"), payload.get("price"), payload.get("category")
    if not name or price is None or not category:
        raise HTTPException(400, "Name, price and category are required")
    if category not in ("pantry", "pottery"):
        raise HTTPException(400, "Invalid category")
    # persist any base64 uploads as files; existing URLs pass through unchanged
    # save_image returns None for an unusable upload — drop those rather than
    # storing a null in the gallery
    images = [u for u in (save_image(i) for i in _clean_images(payload.get("images"))) if u]
    # image_url stays as the primary (first) image, for cart/order snapshots
    image_url = save_image(payload.get("image_url")) or (images[0] if images else None)
    if image_url and not images:
        images = [image_url]
    ptype = (payload.get("type") or "").strip() or None
    # thumbnail is derived server-side from the primary image (managers can't set it)
    thumb_url = make_thumb(image_url)
    row = fetch_one(
        """insert into products (name, name_en, description, description_en, price, sale_price,
                                 unit, unit_en,
                                 category, type, tag, tag_en, image_url, images, thumb_url, stock, sort)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
        [name, _blank_to_none(payload.get("name_en")),
         payload.get("description"), _blank_to_none(payload.get("description_en")),
         price, _sale_price(payload.get("sale_price"), price),
         payload.get("unit"), _blank_to_none(payload.get("unit_en")),
         category, ptype, payload.get("tag"), _blank_to_none(payload.get("tag_en")),
         image_url, Json(images), thumb_url,
         int(payload.get("stock") or 0), int(payload.get("sort") or 0)],
    )
    response.status_code = 201
    return {"product": row}


@router.patch("/{pid}")
def update_product(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    # thumb_url is intentionally NOT accepted from the client — it's derived below
    allowed = ["name", "name_en", "description", "description_en", "price", "sale_price",
               "unit", "unit_en",
               "category", "type", "tag", "tag_en", "image_url", "stock", "is_active", "images", "sort"]
    data = {k: payload[k] for k in (payload or {}) if k in allowed}
    # The two prices only make sense against each other, so whenever either moves the
    # pair is checked as it will end up — including the case that reads as innocent:
    # dropping the usual price to at or below a sale that's already running.
    if "price" in data or "sale_price" in data:
        current = fetch_one("select price, sale_price from products where id = %s", [pid])
        if not current:
            raise HTTPException(404, "Product not found")
        price = data.get("price", current["price"])
        sale = data["sale_price"] if "sale_price" in data else current["sale_price"]
        data["sale_price"] = _sale_price(sale, price)
    # normalize empty type to NULL so it drops out of the filter chips
    if "type" in data:
        data["type"] = (data["type"] or "").strip() or None
    # a cleared translation becomes NULL so the Arabic fallback kicks back in
    for key in ("name_en", "description_en", "unit_en", "tag_en"):
        if key in data:
            data[key] = _blank_to_none(data[key])
    if "sort" in data:
        try:
            data["sort"] = int(data["sort"] or 0)
        except (TypeError, ValueError):
            data["sort"] = 0
    if "images" in data:
        imgs = [u for u in (save_image(i) for i in _clean_images(data["images"])) if u]
        data["images"] = imgs
        # keep the primary image_url in sync with the first gallery image
        if "image_url" not in data:
            data["image_url"] = imgs[0] if imgs else None
    if "image_url" in data:
        data["image_url"] = save_image(data["image_url"])
    # regenerate the list thumbnail whenever the image changes
    if "image_url" in data or "images" in data:
        primary = data.get("image_url")
        if primary is None and data.get("images"):
            primary = data["images"][0]
        data["thumb_url"] = make_thumb(primary)
    if not data:
        raise HTTPException(400, "No fields to update")
    set_clause = ", ".join(f"{f} = %s" for f in data)
    # The CTE snapshots the pre-edit stock in the same statement, so a manual
    # 0 → N edit can fire the waiting list without a second round-trip.
    values = [pid] + [Json(data[f]) if f == "images" else data[f] for f in data] + [pid]
    row = fetch_one(
        f"""with prev as (select stock from products where id = %s)
            update products set {set_clause}, updated_at = now() where id = %s
            returning *, (select stock from prev) as prev_stock""",
        values,
    )
    if not row:
        raise HTTPException(404, "Product not found")
    if row.pop("prev_stock") <= 0 and row["stock"] > 0:
        _fire_stock_alerts(row)
    return {"product": row}


@router.delete("/{pid}")
def delete_product(pid: str, _m=Depends(require_manager)):
    referenced = fetch_one("select 1 from order_items where product_id = %s limit 1", [pid])
    if referenced:
        row = fetch_one("update products set is_active = false where id = %s returning id", [pid])
        if not row:
            raise HTTPException(404, "Product not found")
        return {"removed": "soft"}
    row = fetch_one("delete from products where id = %s returning id", [pid])
    if not row:
        raise HTTPException(404, "Product not found")
    return {"removed": "hard"}


def _fire_stock_alerts(product):
    """Notify (once) everyone waiting on this product, then clear their alerts."""
    waiting = fetch_all("delete from stock_alerts where product_id = %s returning user_id", [product["id"]])
    if not waiting:
        return
    # Plain service wording that points back at the customer's own request.
    # Urgency/marketing phrasing ("order before it runs out") is what browser
    # anti-spam classifiers flag as an unwanted notification.
    notify_users(
        [w["user_id"] for w in waiting],
        type="back_in_stock",
        title="عاد للتوفّر",
        body=f"{product['name']} — طلبتَ أن نُبلغك عند توفّره.",
    )


@router.post("/{pid}/restock")
def restock(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    try:
        qty = int(payload.get("qty"))
    except (TypeError, ValueError):
        qty = 0
    if qty == 0:
        raise HTTPException(400, "Invalid quantity")
    # qty may be negative to reduce stock; never let it drop below zero
    # RETURNING sees the NEW row, so `stock - qty` reconstructs the previous value.
    # Exact for qty > 0 (no clamping can happen there), which is the only case that
    # can bring a sold-out product back and fire the waiting-list alerts.
    row = fetch_one(
        "update products set stock = greatest(0, stock + %s) where id = %s returning *, stock - %s as prev_stock",
        [qty, pid, qty],
    )
    if not row:
        raise HTTPException(404, "Product not found")
    if row.pop("prev_stock") <= 0 and row["stock"] > 0:
        _fire_stock_alerts(row)
    return {"product": row}
