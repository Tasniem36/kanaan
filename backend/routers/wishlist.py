"""Saved products ("favourites"). One row per customer+product; the list returns
the same light product shape the storefront feed uses, so the account page can
render it with the normal product card."""
from fastapi import APIRouter, Depends, HTTPException, Response

from db import execute, fetch_all, fetch_one
from security import current_user

router = APIRouter()

# same light columns as the product feed — thumbnail only, never the full gallery
_COLS = """p.id, p.name, p.name_en, p.description, p.description_en, p.price,
           p.unit, p.unit_en, p.category, p.type, p.tag, p.tag_en,
           coalesce(p.thumb_url, p.image_url) as image_url, p.stock, p.is_active"""


@router.get("")
def list_wishlist(user=Depends(current_user)):
    rows = fetch_all(
        f"""select {_COLS} from wishlists w join products p on p.id = w.product_id
            where w.user_id = %s and p.is_active = true
            order by w.created_at desc""",
        [user["id"]],
    )
    return {"products": rows}


@router.get("/ids")
def list_wishlist_ids(user=Depends(current_user)):
    """Just the ids — what the storefront needs to fill in the hearts. Cheap
    enough to fetch once on sign-in and keep in the store."""
    rows = fetch_all("select product_id from wishlists where user_id = %s", [user["id"]])
    return {"ids": [str(r["product_id"]) for r in rows]}


@router.put("/{pid}")
def add_to_wishlist(pid: str, user=Depends(current_user)):
    if not fetch_one("select 1 as x from products where id = %s and is_active = true", [pid]):
        raise HTTPException(404, "Product not found")
    execute(
        """insert into wishlists (user_id, product_id) values (%s, %s)
           on conflict (user_id, product_id) do nothing""",
        [user["id"], pid],
    )
    return {"saved": True}


@router.delete("/{pid}")
def remove_from_wishlist(pid: str, response: Response, user=Depends(current_user)):
    execute("delete from wishlists where user_id = %s and product_id = %s", [user["id"], pid])
    response.status_code = 204
    return None
