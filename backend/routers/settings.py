from fastapi import APIRouter, Body, Depends, HTTPException
from psycopg.types.json import Json

from db import fetch_one
from security import require_manager
from delivery import get_config

router = APIRouter()


# GET /api/settings/delivery — public: fees + free threshold (checkout needs these)
@router.get("/delivery")
def get_delivery():
    return {"delivery": get_config()}


# PATCH /api/settings/delivery — manager: update fees / free threshold
@router.patch("/delivery")
def update_delivery(_m=Depends(require_manager), payload: dict = Body(default={})):
    cfg = get_config()
    for key in ("fee_high", "fee_low", "free_threshold"):
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
    return {"delivery": cfg}
