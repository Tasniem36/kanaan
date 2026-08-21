from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from psycopg import errors as pg_errors

from db import fetch_all, fetch_one
from audit import log_action
from security import current_user, require_manager

router = APIRouter()


def _kind(payload):
    """The discount this payload describes, validated, as (percent, amount).

    A code is either a percentage off or a fixed number of dirhams off — exactly one,
    because a code carrying both has no single meaning at the checkout.
    """
    has_percent = payload.get("percent") not in (None, "")
    has_amount = payload.get("amount") not in (None, "")
    if has_percent == has_amount:
        raise HTTPException(400, "Set either a percentage or an amount, not both")
    if has_percent:
        try:
            p = int(payload["percent"])
        except (TypeError, ValueError):
            raise HTTPException(400, "Percentage must be a whole number between 1 and 100")
        if p < 1 or p > 100:
            raise HTTPException(400, "Percentage must be between 1 and 100")
        return p, None
    try:
        a = round(float(payload["amount"]), 2)
    except (TypeError, ValueError):
        raise HTTPException(400, "Amount must be a number of dirhams")
    if a <= 0:
        raise HTTPException(400, "Amount must be more than zero")
    return None, a


def error_body(r):
    """What a rejected code tells the customer.

    Usually the sentence alone. When the code would work on a bigger basket it also
    carries the numbers, so the storefront can ask for the difference in Arabic
    instead of showing the English fallback.
    """
    if not r.get("reason"):
        return r["error"]
    return {"error": r["error"], "reason": r["reason"],
            "amount": r.get("amount"), "short": r.get("short")}


def evaluate_code(run, code, user_id, subtotal):
    """`run(sql, params) -> list[dict]`. Returns {dc, percent, amount, discount} or
    {error}. `discount` is always dirhams off, whichever kind the code is."""
    if not code:
        return {"discount": 0}
    rows = run("select * from discount_codes where code = %s", [str(code).upper().strip()])
    dc = rows[0] if rows else None
    if not dc or not dc["active"]:
        return {"error": "Invalid discount code"}
    if dc["expires_at"] and dc["expires_at"] < datetime.now(timezone.utc):
        return {"error": "This discount code has expired"}
    if dc["max_uses"] is not None and dc["used_count"] >= dc["max_uses"]:
        return {"error": "This code has reached its usage limit"}
    if dc["first_order_only"]:
        c = run("select count(*)::int as n from orders where user_id = %s and status <> 'cancelled'", [user_id])
        if c[0]["n"] > 0:
            return {"error": "This code is valid on your first order only"}
    if dc["amount"] is not None:
        amount, basket = round(float(dc["amount"]), 2), round(float(subtotal), 2)
        if amount > basket:
            # The code is worth more than the basket. Shrinking it to fit would quietly
            # hand over the difference; saying so instead turns it into a reason to add
            # something. `short` is what the basket needs to reach, so the storefront
            # can ask for it in the customer's own language.
            return {"error": f"This code takes {amount:g} off — add {round(amount - basket, 2):g} "
                             f"more to your basket to use it",
                    "reason": "min_basket", "amount": amount, "short": round(amount - basket, 2)}
        discount = amount
    else:
        discount = round(float(subtotal) * dc["percent"]) / 100
    return {"dc": dc, "percent": dc["percent"], "amount": dc["amount"], "discount": discount}


@router.post("/validate")
def validate(request: Request, user=Depends(current_user), payload: dict = Body(default={})):
    r = evaluate_code(lambda sql, p: fetch_all(sql, p), payload.get("code"),
                      user["id"], float(payload.get("subtotal") or 0))
    if r.get("error"):
        # a code that doesn't work is a customer at the checkout expecting a discount
        log_action(user_id=user["id"], action="promo_invalid",
                   detail={"code": str(payload.get("code") or "")[:40], "reason": r["error"]},
                   request=request)
        raise HTTPException(400, error_body(r))
    # `percent` is null for a fixed-amount code, so the checkout knows which of the
    # two it's showing; `discount` is the dirhams off either way.
    return {"valid": True, "percent": r["percent"], "amount": r["amount"],
            "discount": r["discount"], "code": r["dc"]["code"]}


@router.get("")
def list_codes(_m=Depends(require_manager)):
    return {"codes": fetch_all("select * from discount_codes order by created_at desc")}


@router.post("")
def create_code(response: Response, _m=Depends(require_manager), payload: dict = Body(default={})):
    code = payload.get("code")
    if not code:
        raise HTTPException(400, "A code is required")
    percent, amount = _kind(payload)
    try:
        row = fetch_one(
            """insert into discount_codes (code, percent, amount, first_order_only, active, max_uses, expires_at)
               values (%s, %s, %s, %s, %s, %s, %s) returning *""",
            [str(code).upper().strip(), percent, amount,
             payload.get("first_order_only", True) is not False,
             payload.get("active", True) is not False,
             int(payload["max_uses"]) if payload.get("max_uses") else None,
             payload.get("expires_at") or None],
        )
    except pg_errors.UniqueViolation:
        raise HTTPException(409, "This code already exists")
    response.status_code = 201
    return {"code": row}


@router.patch("/{cid}")
def update_code(cid: str, _m=Depends(require_manager), payload: dict = Body(default={})):
    allowed = ["first_order_only", "active", "max_uses", "expires_at"]
    fields = [k for k in (payload or {}) if k in allowed]
    values = [payload[f] for f in fields]
    # Switching a code between the two kinds means writing both columns: the one being
    # set and the one being cleared. Handled here rather than by letting a caller send
    # them separately, which would leave the row with two discounts or none.
    if "percent" in (payload or {}) or "amount" in (payload or {}):
        percent, amount = _kind(payload)
        fields += ["percent", "amount"]
        values += [percent, amount]
    if not fields:
        raise HTTPException(400, "No fields to update")
    set_clause = ", ".join(f"{f} = %s" for f in fields)
    values = values + [cid]
    row = fetch_one(f"update discount_codes set {set_clause} where id = %s returning *", values)
    if not row:
        raise HTTPException(404, "Code not found")
    return {"code": row}


@router.delete("/{cid}")
def delete_code(cid: str, response: Response, _m=Depends(require_manager)):
    row = fetch_one("delete from discount_codes where id = %s returning id", [cid])
    if not row:
        raise HTTPException(404, "Code not found")
    response.status_code = 204
    return None
