from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from db import fetch_all, fetch_one
from security import optional_user, require_manager
from audit import log_action

router = APIRouter()


@router.get("")
def list_products(request: Request):
    user = optional_user(request)
    is_manager = user and user.get("role") == "manager"
    where = "" if is_manager else "where is_active = true"
    rows = fetch_all(
        f"""select id, name, description, price, unit, category, tag, image_url, stock, is_active
            from products {where} order by created_at"""
    )
    # server-side "opened the storefront" signal (shoppers/guests, not managers)
    if not is_manager:
        log_action(user_id=(user or {}).get("id"), action="visit",
                   detail={"ua": request.headers.get("user-agent")}, request=request)
    return {"products": rows}


@router.post("")
def create_product(response: Response, _m=Depends(require_manager), payload: dict = Body(default={})):
    name, price, category = payload.get("name"), payload.get("price"), payload.get("category")
    if not name or price is None or not category:
        raise HTTPException(400, "الاسم والسعر والقسم مطلوبة")
    if category not in ("pantry", "pottery"):
        raise HTTPException(400, "قسم غير صالح")
    row = fetch_one(
        """insert into products (name, description, price, unit, category, tag, image_url, stock)
           values (%s, %s, %s, %s, %s, %s, %s, %s) returning *""",
        [name, payload.get("description"), price, payload.get("unit"), category,
         payload.get("tag"), payload.get("image_url"), int(payload.get("stock") or 0)],
    )
    response.status_code = 201
    return {"product": row}


@router.patch("/{pid}")
def update_product(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    allowed = ["name", "description", "price", "unit", "category", "tag", "image_url", "stock", "is_active"]
    fields = [k for k in (payload or {}) if k in allowed]
    if not fields:
        raise HTTPException(400, "لا توجد حقول للتحديث")
    set_clause = ", ".join(f"{f} = %s" for f in fields)
    values = [payload[f] for f in fields] + [pid]
    row = fetch_one(f"update products set {set_clause} where id = %s returning *", values)
    if not row:
        raise HTTPException(404, "المنتج غير موجود")
    return {"product": row}


@router.delete("/{pid}")
def delete_product(pid: str, _m=Depends(require_manager)):
    referenced = fetch_one("select 1 from order_items where product_id = %s limit 1", [pid])
    if referenced:
        row = fetch_one("update products set is_active = false where id = %s returning id", [pid])
        if not row:
            raise HTTPException(404, "المنتج غير موجود")
        return {"removed": "soft"}
    row = fetch_one("delete from products where id = %s returning id", [pid])
    if not row:
        raise HTTPException(404, "المنتج غير موجود")
    return {"removed": "hard"}


@router.post("/{pid}/restock")
def restock(pid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    try:
        qty = int(payload.get("qty"))
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        raise HTTPException(400, "كمية غير صالحة")
    row = fetch_one("update products set stock = stock + %s where id = %s returning *", [qty, pid])
    if not row:
        raise HTTPException(404, "المنتج غير موجود")
    return {"product": row}
