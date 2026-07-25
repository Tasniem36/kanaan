from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from db import pool, fetch_all, fetch_one
from security import current_user
from audit import log_action

router = APIRouter()


@router.get("")
def list_addresses(user=Depends(current_user)):
    rows = fetch_all("select * from addresses where user_id = %s order by is_default desc, created_at", [user["id"]])
    return {"addresses": rows}


@router.post("")
def add_address(request: Request, response: Response, user=Depends(current_user), payload: dict = Body(default={})):
    city, street, house = payload.get("city"), payload.get("street"), payload.get("house")
    if not city or not street or not house:
        raise HTTPException(400, "City, street and house number are required")
    is_default = bool(payload.get("is_default"))
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        if is_default:
            cur.execute("update addresses set is_default = false where user_id = %s", [user["id"]])
        cur.execute(
            """insert into addresses (user_id, label, city, street, house, notes, is_default)
               values (%s, %s, %s, %s, %s, %s, %s) returning *""",
            [user["id"], payload.get("label"), city, street, house, payload.get("notes"), is_default],
        )
        address = cur.fetchone()
    log_action(user_id=user["id"], action="address_added", detail={"city": city}, request=request)
    response.status_code = 201
    return {"address": address}


@router.patch("/{aid}")
def update_address(aid: str, user=Depends(current_user), payload: dict = Body(default={})):
    allowed = ["label", "city", "street", "house", "notes", "is_default"]
    fields = [k for k in (payload or {}) if k in allowed]
    if not fields:
        raise HTTPException(400, "No fields to update")
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        if payload.get("is_default"):
            cur.execute("update addresses set is_default = false where user_id = %s", [user["id"]])
        set_clause = ", ".join(f"{f} = %s" for f in fields)
        values = [payload[f] for f in fields] + [aid, user["id"]]
        cur.execute(f"update addresses set {set_clause} where id = %s and user_id = %s returning *", values)
        address = cur.fetchone()
    if not address:
        raise HTTPException(404, "Address not found")
    return {"address": address}


@router.delete("/{aid}")
def delete_address(aid: str, response: Response, request: Request, user=Depends(current_user)):
    row = fetch_one("delete from addresses where id = %s and user_id = %s returning id", [aid, user["id"]])
    if not row:
        raise HTTPException(404, "Address not found")
    log_action(user_id=user["id"], action="address_removed", request=request)
    response.status_code = 204
    return None
