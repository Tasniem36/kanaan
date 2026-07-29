from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from psycopg.types.json import Json

from db import fetch_all, fetch_one
from security import optional_user, require_manager
from audit import log_action
from media import save_image, make_thumb

router = APIRouter()


def _clean_images(value):
    """Keep only non-empty string entries, preserving order."""
    if not isinstance(value, list):
        return []
    return [s for s in value if isinstance(s, str) and s.strip()]


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
        # customer name search (case-insensitive substring)
        conds.append("name ilike %s")
        params.append(f"%{search}%")
    where = ("where " + " and ".join(conds)) if conds else ""

    # LIGHT payload: only a small thumbnail, never the heavy data-URL gallery
    # (the full images load on demand via GET /products/{id}).
    if is_manager and not force_active:
        cols = ("id, name, description, price, unit, category, type, tag, "
                "coalesce(thumb_url, image_url) as image_url, thumb_url, stock, is_active")
    else:
        cols = ("id, name, description, price, unit, category, type, tag, "
                "coalesce(thumb_url, image_url) as image_url, stock, is_active")

    total = fetch_one(f"select count(*)::int as n from products {where}", params)["n"]

    sql = f"select {cols} from products {where} order by created_at"
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
    # "opened the storefront" signal — shoppers only, once per feed (first page)
    if not is_manager and first_page:
        log_action(user_id=(user or {}).get("id"), action="visit",
                   detail={"ua": request.headers.get("user-agent")}, request=request)
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


@router.get("/{pid}")
def get_product(pid: str, request: Request):
    user = optional_user(request)
    is_manager = user and user.get("role") == "manager"
    row = fetch_one(
        """select id, name, description, price, unit, category, type, tag, image_url, images, thumb_url, stock, is_active
           from products where id = %s""", [pid])
    if not row or (not is_manager and not row["is_active"]):
        raise HTTPException(404, "Product not found")
    return {"product": row}


@router.post("")
def create_product(response: Response, _m=Depends(require_manager), payload: dict = Body(default={})):
    name, price, category = payload.get("name"), payload.get("price"), payload.get("category")
    if not name or price is None or not category:
        raise HTTPException(400, "Name, price and category are required")
    if category not in ("pantry", "pottery"):
        raise HTTPException(400, "Invalid category")
    # persist any base64 uploads as files; existing URLs pass through unchanged
    images = [save_image(i) for i in _clean_images(payload.get("images"))]
    # image_url stays as the primary (first) image, for cart/order snapshots
    image_url = save_image(payload.get("image_url")) or (images[0] if images else None)
    if image_url and not images:
        images = [image_url]
    ptype = (payload.get("type") or "").strip() or None
    # thumbnail is derived server-side from the primary image (managers can't set it)
    thumb_url = make_thumb(image_url)
    row = fetch_one(
        """insert into products (name, description, price, unit, category, type, tag, image_url, images, thumb_url, stock)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
        [name, payload.get("description"), price, payload.get("unit"), category, ptype,
         payload.get("tag"), image_url, Json(images), thumb_url,
         int(payload.get("stock") or 0)],
    )
    response.status_code = 201
    return {"product": row}


@router.patch("/{pid}")
def update_product(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    # thumb_url is intentionally NOT accepted from the client — it's derived below
    allowed = ["name", "description", "price", "unit", "category", "type", "tag", "image_url", "stock", "is_active", "images"]
    data = {k: payload[k] for k in (payload or {}) if k in allowed}
    # normalize empty type to NULL so it drops out of the filter chips
    if "type" in data:
        data["type"] = (data["type"] or "").strip() or None
    if "images" in data:
        imgs = [save_image(i) for i in _clean_images(data["images"])]
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
    values = [Json(data[f]) if f == "images" else data[f] for f in data] + [pid]
    row = fetch_one(f"update products set {set_clause} where id = %s returning *", values)
    if not row:
        raise HTTPException(404, "Product not found")
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


@router.post("/{pid}/restock")
def restock(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    try:
        qty = int(payload.get("qty"))
    except (TypeError, ValueError):
        qty = 0
    if qty == 0:
        raise HTTPException(400, "Invalid quantity")
    # qty may be negative to reduce stock; never let it drop below zero
    row = fetch_one(
        "update products set stock = greatest(0, stock + %s) where id = %s returning *",
        [qty, pid],
    )
    if not row:
        raise HTTPException(404, "Product not found")
    return {"product": row}
