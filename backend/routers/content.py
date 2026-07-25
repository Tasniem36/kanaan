from fastapi import APIRouter, Body, Depends, HTTPException

from db import fetch_all, fetch_one
from security import require_manager

router = APIRouter()

_EDITABLE = [
    "image_url", "link", "sort",
    "title_ar", "title_en", "desc_ar", "desc_en", "more_ar", "more_en",
]


# GET /api/content/values — public: the "why us" cards for the storefront
@router.get("/values")
def list_values():
    return {"values": fetch_all("select * from content_values order by sort, updated_at")}


# PATCH /api/content/values/{vid} — manager: edit a card's text / image
@router.patch("/values/{vid}")
def update_value(vid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    data = {k: payload[k] for k in (payload or {}) if k in _EDITABLE}
    if not data:
        raise HTTPException(400, "No fields to update")
    set_clause = ", ".join(f"{f} = %s" for f in data) + ", updated_at = now()"
    values = list(data.values()) + [vid]
    row = fetch_one(f"update content_values set {set_clause} where id = %s returning *", values)
    if not row:
        raise HTTPException(404, "Card not found")
    return {"value": row}


# DELETE /api/content/values/{vid} — manager: remove a card
@router.delete("/values/{vid}")
def delete_value(vid: str, _m=Depends(require_manager)):
    row = fetch_one("delete from content_values where id = %s returning id", [vid])
    if not row:
        raise HTTPException(404, "Card not found")
    return {"ok": True}
