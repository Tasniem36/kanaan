from fastapi import APIRouter, Body, Depends, HTTPException
from psycopg.types.json import Json

from db import fetch_all, fetch_one
from security import require_manager

router = APIRouter()

_EDITABLE = [
    "image_url", "link", "sort",
    "title_ar", "title_en", "desc_ar", "desc_en", "more_ar", "more_en",
]

# Editable headings for storefront sections, kept in the settings table under
# 'section:<key>'. Only these keys exist — an unknown one 404s rather than filling
# settings with junk. A blank field means "use the bundled translation".
_SECTION_KEYS = ("reviews",)
_SECTION_FIELDS = {
    "eyebrow_ar": 120, "eyebrow_en": 120,   # field -> max length
    "title_ar": 160, "title_en": 160,
    "desc_ar": 600, "desc_en": 600,
}


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


# GET /api/content/sections — public: every section's edited headings, keyed by
# section ('reviews'), so the storefront needs one request for the lot
@router.get("/sections")
def list_sections():
    rows = fetch_all("select key, value from settings where key like %s", ["section:%"])
    return {"sections": {r["key"].split(":", 1)[1]: (r["value"] or {}) for r in rows}}


# PATCH /api/content/sections/{key} — manager: edit one section's headings
@router.patch("/sections/{key}")
def update_section(key: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    if key not in _SECTION_KEYS:
        raise HTTPException(404, "Unknown section")
    # a full replace, not a merge: the form always posts all six fields, and
    # clearing one is how the manager goes back to the bundled translation
    copy = {f: " ".join(str((payload or {}).get(f) or "").split())[:cap]
            for f, cap in _SECTION_FIELDS.items()}
    # the manager's own show/hide switch for the section, independent of whether
    # there is anything in it yet (the storefront hides an empty section anyway)
    copy["hidden"] = bool((payload or {}).get("hidden"))
    fetch_one(
        """insert into settings (key, value) values (%s, %s)
           on conflict (key) do update set value = excluded.value, updated_at = now()
           returning key""",
        [f"section:{key}", Json(copy)],
    )
    return {"section": copy}
