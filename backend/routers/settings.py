from fastapi import APIRouter, Body, Depends, HTTPException, Response
from psycopg.types.json import Json

from db import fetch_one
from security import require_manager
from delivery import get_config, get_zones

router = APIRouter()


# GET /api/settings/delivery — public: global config + zones (checkout needs these)
@router.get("/delivery")
def get_delivery():
    cfg = get_config()
    cfg["zones"] = get_zones()
    return {"delivery": cfg}


# PATCH /api/settings/delivery — manager: update global config (threshold, default fee)
@router.patch("/delivery")
def update_delivery(_m=Depends(require_manager), payload: dict = Body(default={})):
    cfg = get_config()
    for key in ("free_threshold", "default_fee"):
        if key in payload:
            try:
                cfg[key] = max(0, round(float(payload[key]), 2))
            except (TypeError, ValueError):
                raise HTTPException(400, f"Invalid value for {key}")
    fetch_one(
        """insert into settings (key, value) values ('delivery', %s)
           on conflict (key) do update set value = excluded.value, updated_at = now()
           returning value""",
        [Json(cfg)],
    )
    cfg["zones"] = get_zones()
    return {"delivery": cfg}


# ---- delivery zones CRUD (manager) ----------------------------------------
@router.post("/delivery/zones")
def create_zone(response: Response, _m=Depends(require_manager), payload: dict = Body(default={})):
    label = (payload.get("label") or "").strip()
    if not label:
        raise HTTPException(400, "Zone name is required")
    try:
        fee = max(0, round(float(payload.get("fee")), 2))
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid fee")
    row = fetch_one(
        "insert into delivery_zones (label, keywords, fee, sort) values (%s, %s, %s, %s) returning *",
        [label, (payload.get("keywords") or "").strip(), fee, int(payload.get("sort") or 0)],
    )
    response.status_code = 201
    return {"zone": row}


@router.patch("/delivery/zones/{zid}")
def update_zone(zid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    allowed = ["label", "keywords", "fee", "sort"]
    data = {k: payload[k] for k in (payload or {}) if k in allowed}
    if not data:
        raise HTTPException(400, "No fields to update")
    if "fee" in data:
        try:
            data["fee"] = max(0, round(float(data["fee"]), 2))
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid fee")
    set_clause = ", ".join(f"{f} = %s" for f in data)
    row = fetch_one(f"update delivery_zones set {set_clause} where id = %s returning *",
                    list(data.values()) + [zid])
    if not row:
        raise HTTPException(404, "Zone not found")
    return {"zone": row}


@router.delete("/delivery/zones/{zid}")
def delete_zone(zid: str, _m=Depends(require_manager)):
    row = fetch_one("delete from delivery_zones where id = %s returning id", [zid])
    if not row:
        raise HTTPException(404, "Zone not found")
    return {"ok": True}
