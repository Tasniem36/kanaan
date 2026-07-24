from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from psycopg import errors as pg_errors

from db import fetch_all, fetch_one
from security import current_user, require_manager

router = APIRouter()


def evaluate_code(run, code, user_id, subtotal):
    """`run(sql, params) -> list[dict]`. Returns {dc, percent, discount} or {error}."""
    if not code:
        return {"discount": 0}
    rows = run("select * from discount_codes where code = %s", [str(code).upper().strip()])
    dc = rows[0] if rows else None
    if not dc or not dc["active"]:
        return {"error": "كود الخصم غير صالح"}
    if dc["expires_at"] and dc["expires_at"] < datetime.now(timezone.utc):
        return {"error": "انتهت صلاحية كود الخصم"}
    if dc["max_uses"] is not None and dc["used_count"] >= dc["max_uses"]:
        return {"error": "انتهت مرّات استخدام هذا الكود"}
    if dc["first_order_only"]:
        c = run("select count(*)::int as n from orders where user_id = %s and status <> 'cancelled'", [user_id])
        if c[0]["n"] > 0:
            return {"error": "هذا الكود صالحٌ للطلب الأوّل فقط"}
    discount = round(float(subtotal) * dc["percent"]) / 100
    return {"dc": dc, "percent": dc["percent"], "discount": discount}


@router.post("/validate")
def validate(user=Depends(current_user), payload: dict = Body(default={})):
    r = evaluate_code(lambda sql, p: fetch_all(sql, p), payload.get("code"),
                      user["id"], float(payload.get("subtotal") or 0))
    if r.get("error"):
        raise HTTPException(400, r["error"])
    return {"valid": True, "percent": r["percent"], "discount": r["discount"], "code": r["dc"]["code"]}


@router.get("")
def list_codes(_m=Depends(require_manager)):
    return {"codes": fetch_all("select * from discount_codes order by created_at desc")}


@router.post("")
def create_code(response: Response, _m=Depends(require_manager), payload: dict = Body(default={})):
    code, percent = payload.get("code"), payload.get("percent")
    if not code or not percent:
        raise HTTPException(400, "الكود والنسبة مطلوبان")
    try:
        p = int(percent)
    except (TypeError, ValueError):
        p = 0
    if p < 1 or p > 100:
        raise HTTPException(400, "النسبة يجب أن تكون بين ١ و ١٠٠")
    try:
        row = fetch_one(
            """insert into discount_codes (code, percent, first_order_only, active, max_uses, expires_at)
               values (%s, %s, %s, %s, %s, %s) returning *""",
            [str(code).upper().strip(), p, payload.get("first_order_only", True) is not False,
             payload.get("active", True) is not False,
             int(payload["max_uses"]) if payload.get("max_uses") else None,
             payload.get("expires_at") or None],
        )
    except pg_errors.UniqueViolation:
        raise HTTPException(409, "هذا الكود موجودٌ مسبقًا")
    response.status_code = 201
    return {"code": row}


@router.patch("/{cid}")
def update_code(cid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    allowed = ["percent", "first_order_only", "active", "max_uses", "expires_at"]
    fields = [k for k in (payload or {}) if k in allowed]
    if not fields:
        raise HTTPException(400, "لا توجد حقول للتحديث")
    set_clause = ", ".join(f"{f} = %s" for f in fields)
    values = [payload[f] for f in fields] + [cid]
    row = fetch_one(f"update discount_codes set {set_clause} where id = %s returning *", values)
    if not row:
        raise HTTPException(404, "الكود غير موجود")
    return {"code": row}


@router.delete("/{cid}")
def delete_code(cid: str, response: Response, _m=Depends(require_manager)):
    row = fetch_one("delete from discount_codes where id = %s returning id", [cid])
    if not row:
        raise HTTPException(404, "الكود غير موجود")
    response.status_code = 204
    return None
