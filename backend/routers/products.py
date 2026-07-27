from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from psycopg.types.json import Json

from db import fetch_all, fetch_one
from security import optional_user, require_manager
from audit import log_action

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

    conds, params = [], []
    if not is_manager or force_active:
        conds.append("is_active = true")
    if category in ("pantry", "pottery"):
        conds.append("category = %s")
        params.append(category)
    where = ("where " + " and ".join(conds)) if conds else ""

    # LIGHT payload: only a small thumbnail, never the heavy data-URL gallery
    # (the full images load on demand via GET /products/{id}).
    if is_manager and not force_active:
        cols = ("id, name, description, price, unit, category, tag, "
                "coalesce(thumb_url, image_url) as image_url, thumb_url, stock, is_active")
    else:
        cols = ("id, name, description, price, unit, category, tag, "
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


@router.get("/{pid}")
def get_product(pid: str, request: Request):
    user = optional_user(request)
    is_manager = user and user.get("role") == "manager"
    row = fetch_one(
        """select id, name, description, price, unit, category, tag, image_url, images, thumb_url, stock, is_active
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
    images = _clean_images(payload.get("images"))
    # image_url stays as the primary (first) image, for cart/order snapshots
    image_url = payload.get("image_url") or (images[0] if images else None)
    if image_url and not images:
        images = [image_url]
    row = fetch_one(
        """insert into products (name, description, price, unit, category, tag, image_url, images, thumb_url, stock)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
        [name, payload.get("description"), price, payload.get("unit"), category,
         payload.get("tag"), image_url, Json(images), payload.get("thumb_url") or image_url,
         int(payload.get("stock") or 0)],
    )
    response.status_code = 201
    return {"product": row}


@router.patch("/{pid}")
def update_product(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    allowed = ["name", "description", "price", "unit", "category", "tag", "image_url", "stock", "is_active", "images", "thumb_url"]
    data = {k: payload[k] for k in (payload or {}) if k in allowed}
    if "images" in data:
        imgs = _clean_images(data["images"])
        data["images"] = imgs
        # keep the primary image_url in sync with the first gallery image
        if "image_url" not in data:
            data["image_url"] = imgs[0] if imgs else None
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
