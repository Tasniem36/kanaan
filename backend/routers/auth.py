import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from psycopg import errors as pg_errors

from db import fetch_one, execute
from security import hash_password, verify_password, sign_token, current_user
from validate import is_email, is_strong_password, normalize_uae_phone
from audit import log_action
from ratelimit import rate_limit
from messaging import send_email, send_phone_code, email_configured, phone_configured

router = APIRouter()

_IS_PROD = os.getenv("ENV", "").lower() in ("prod", "production")
VERIFY_TTL_MIN = 10
WEAK_PW_MSG = "Weak password: at least 8 characters with an uppercase letter, a lowercase letter, and a number"


def _code():
    return f"{secrets.randbelow(1000000):06d}"


def _required_channels():
    """Which channels must be verified. A channel is enforced only if its provider
    is configured — so a missing/broken provider degrades gracefully instead of
    locking everyone out. Locally (non-prod) with nothing configured we still
    require both, so the flow stays testable via the dev-echoed codes."""
    e, s = email_configured(), phone_configured()
    if not _IS_PROD and not e and not s:
        return True, True
    return e, s


def _create_user(email, password_hash, full_name, phone, request):
    user = fetch_one(
        """insert into users (email, password_hash, full_name, phone)
           values (%s, %s, %s, %s) returning id, email, full_name, phone, role""",
        [email, password_hash, full_name, phone],
    )
    log_action(user_id=user["id"], action="register", request=request)
    return {"verified": True, "token": sign_token(user), "user": public_user(user)}


def _send_codes(email, phone, email_code, phone_code):
    """Send both codes (best-effort). In non-prod, unsent codes are printed so the
    flow is testable without real providers; returns (email_sent, sms_sent)."""
    subject = "رمز التحقق — دكّان كنعان"
    body = (f"مرحباً،\n\nرمز التحقق الخاص بك في دكّان كنعان هو: {email_code}\n"
            f"الرمز صالحٌ لمدة {VERIFY_TTL_MIN} دقائق.\n\nإن لم تطلب هذا الرمز فتجاهل هذه الرسالة.")
    email_sent = send_email(email, subject, body)
    phone_sent = send_phone_code(phone, phone_code)
    if not email_sent:
        print(f"[verify] EMAIL code for {email}: {email_code}")
    if not phone_sent:
        print(f"[verify] PHONE code for {phone}: {phone_code}")
    return email_sent, phone_sent


def public_user(u):
    return {"id": u["id"], "email": u["email"], "full_name": u["full_name"], "phone": u["phone"], "role": u["role"]}


# Step 1: validate the details, stash a pending signup, and send email + SMS codes.
@router.post("/register")
def register_start(request: Request, payload: dict = Body(default={})):
    rate_limit(request, bucket="register", limit=5, window=60)
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Email and password are required")
    if len(password) > 200:
        # bcrypt silently truncates at 72 bytes; also guard against hashing-cost DoS.
        raise HTTPException(400, "Password is too long")
    if not is_email(email):
        raise HTTPException(400, "Invalid email address")
    phone_norm = normalize_uae_phone(payload.get("phone"))
    if not phone_norm:
        raise HTTPException(400, "Invalid UAE phone number")
    if not is_strong_password(password):
        raise HTTPException(400, WEAK_PW_MSG)
    if fetch_one("select 1 from users where email = %s", [email]):
        raise HTTPException(409, "This email is already registered")

    pw_hash = hash_password(password)
    email_req, phone_req = _required_channels()
    if not email_req and not phone_req:
        # no verification channel available → create the account directly (a broken
        # or unconfigured provider must never block sales)
        try:
            return _create_user(email, pw_hash, payload.get("full_name"), phone_norm, request)
        except pg_errors.UniqueViolation:
            raise HTTPException(409, "This email is already registered")

    ec, pc = _code(), _code()
    execute("delete from signup_verifications where lower(email) = %s", [email])
    row = fetch_one(
        """insert into signup_verifications
             (email, phone, full_name, password_hash, email_code, phone_code, email_ok, phone_ok, expires_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s, now() + %s * interval '1 minute') returning id""",
        [email, phone_norm, payload.get("full_name"), pw_hash, ec, pc,
         not email_req, not phone_req, VERIFY_TTL_MIN],
    )
    resp = {"verification_id": str(row["id"]), "email": email, "phone": phone_norm,
            "email_required": email_req, "phone_required": phone_req}
    dev = {}
    if email_req:
        resp["email_sent"] = send_email(email, "رمز التحقق — دكّان كنعان",
                                        f"رمز التحقق الخاص بك في دكّان كنعان هو: {ec}\nصالحٌ لمدة {VERIFY_TTL_MIN} دقائق.")
        if not resp["email_sent"]:
            print(f"[verify] EMAIL code for {email}: {ec}")
        dev["email"] = ec
    if phone_req:
        resp["phone_sent"] = send_phone_code(phone_norm, pc)
        if not resp["phone_sent"]:
            print(f"[verify] PHONE code for {phone_norm}: {pc}")
        dev["phone"] = pc
    if not _IS_PROD:  # let local testing proceed without real providers
        resp["dev_codes"] = dev
    return resp


# Step 2: check both codes; only then create the real account and log the user in.
@router.post("/register/verify")
def register_verify(request: Request, payload: dict = Body(default={})):
    vid = payload.get("verification_id")
    ec = (payload.get("email_code") or "").strip()
    pc = (payload.get("phone_code") or "").strip()
    if not vid:
        raise HTTPException(400, "Missing verification")
    v = fetch_one("select * from signup_verifications where id = %s", [vid])
    if not v:
        raise HTTPException(400, "Verification expired — please start again")
    if v["expires_at"] < datetime.now(timezone.utc):
        execute("delete from signup_verifications where id = %s", [vid])
        raise HTTPException(400, "The codes have expired — please resend")
    if v["attempts"] >= 8:
        execute("delete from signup_verifications where id = %s", [vid])
        raise HTTPException(429, "Too many attempts — please start again")
    execute("update signup_verifications set attempts = attempts + 1 where id = %s", [vid])

    email_ok = v["email_ok"] or (bool(ec) and ec == v["email_code"])
    phone_ok = v["phone_ok"] or (bool(pc) and pc == v["phone_code"])
    execute("update signup_verifications set email_ok = %s, phone_ok = %s where id = %s",
            [email_ok, phone_ok, vid])
    if not (email_ok and phone_ok):
        return {"verified": False, "email_ok": email_ok, "phone_ok": phone_ok}

    try:
        user = fetch_one(
            """insert into users (email, password_hash, full_name, phone)
               values (%s, %s, %s, %s) returning id, email, full_name, phone, role""",
            [v["email"], v["password_hash"], v["full_name"], v["phone"]],
        )
    except pg_errors.UniqueViolation:
        execute("delete from signup_verifications where id = %s", [vid])
        raise HTTPException(409, "This email is already registered")
    execute("delete from signup_verifications where id = %s", [vid])
    log_action(user_id=user["id"], action="register", request=request)
    return {"verified": True, "token": sign_token(user), "user": public_user(user)}


# Resend fresh codes for an in-progress signup.
@router.post("/register/resend")
def register_resend(request: Request, payload: dict = Body(default={})):
    rate_limit(request, bucket="register", limit=5, window=60)
    vid = payload.get("verification_id")
    v = fetch_one("select * from signup_verifications where id = %s", [vid]) if vid else None
    if not v:
        raise HTTPException(400, "Verification expired — please start again")
    ec, pc = _code(), _code()
    execute("""update signup_verifications
                 set email_code = %s, phone_code = %s, attempts = 0,
                     expires_at = now() + %s * interval '1 minute'
               where id = %s""", [ec, pc, VERIFY_TTL_MIN, vid])
    email_sent, sms_sent = _send_codes(v["email"], v["phone"], ec, pc)
    resp = {"email_sent": email_sent, "phone_sent": sms_sent}
    if not _IS_PROD:
        resp["dev_codes"] = {"email": ec, "phone": pc}
    return resp


@router.post("/login")
def login(request: Request, payload: dict = Body(default={})):
    rate_limit(request, bucket="login", limit=10, window=60)
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Email and password are required")
    user = fetch_one("select * from users where email = %s", [email])
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid login credentials")
    log_action(user_id=user["id"], action="login", request=request)
    return {"token": sign_token(user), "user": public_user(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    row = fetch_one("select id, email, full_name, phone, role from users where id = %s", [user["id"]])
    if not row:
        raise HTTPException(404, "User not found")
    return {"user": row}
