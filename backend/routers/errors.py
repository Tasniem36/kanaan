"""Customer-side error reports. The frontend posts any error a customer hits
(with their contact, if logged in) so the admin can follow up and make sure no
one is left blocked."""
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from db import fetch_all, fetch_one, execute
from security import optional_user, require_manager
from ratelimit import rate_limit

router = APIRouter()


@router.post("")
def report_error(request: Request, payload: dict = Body(default={})):
    rate_limit(request, bucket="error_report", limit=20, window=60)
    message = (payload.get("message") or "").strip()[:1000]
    if not message:
        raise HTTPException(400, "Empty report")
    detail = (payload.get("detail") or "").strip()[:4000] or None
    page = (payload.get("page") or "").strip()[:300] or None
    ua = (request.headers.get("user-agent") or "")[:400] or None

    user = optional_user(request)
    uid = user["id"] if user else None
    name = email = phone = None
    if uid:
        row = fetch_one("select full_name, email, phone from users where id = %s", [uid])
        if row:
            name, email, phone = row["full_name"], row["email"], row["phone"]

    execute(
        """insert into error_reports (user_id, name, email, phone, message, detail, page, user_agent)
           values (%s, %s, %s, %s, %s, %s, %s, %s)""",
        [uid, name, email, phone, message, detail, page, ua],
    )
    return {"ok": True}


@router.get("")
def list_errors(_m=Depends(require_manager)):
    rows = fetch_all(
        """select id, user_id, name, email, phone, message, detail, page, user_agent, created_at
           from error_reports order by created_at desc limit 200"""
    )
    return {"errors": rows}


@router.delete("/{eid}")
def dismiss_error(eid: str, _m=Depends(require_manager)):
    execute("delete from error_reports where id = %s", [eid])
    return {"ok": True}
