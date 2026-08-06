"""Server-side cart so a logged-in customer's basket follows them across devices.
Stores the cart line map ({ productId: { product, qty } }) as-is."""
from fastapi import APIRouter, Body, Depends, HTTPException
from psycopg.types.json import Json

from db import fetch_one, execute
from security import current_user

router = APIRouter()


@router.get("")
def get_cart(user=Depends(current_user)):
    row = fetch_one("select items from carts where user_id = %s", [user["id"]])
    return {"items": row["items"] if row else {}}


@router.put("")
def save_cart(user=Depends(current_user), payload: dict = Body(default={})):
    items = payload.get("items")
    if not isinstance(items, dict):
        raise HTTPException(400, "Invalid cart")
    if len(items) > 100:  # sanity cap
        raise HTTPException(400, "Cart too large")
    execute(
        """insert into carts (user_id, items, updated_at) values (%s, %s, now())
           on conflict (user_id) do update set items = excluded.items, updated_at = now()""",
        [user["id"], Json(items)],
    )
    return {"ok": True}
