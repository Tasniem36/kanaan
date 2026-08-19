import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from db import fetch_one, execute
from security import hash_password, verify_password, sign_token, current_user
from validate import is_email, is_strong_password, normalize_uae_phone
from audit import log_action
from ratelimit import rate_limit
from messaging import send_email, send_sms, email_configured, sms_configured

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
    e, s = email_configured(), sms_configured()
    if not _IS_PROD and not e and not s:
        return True, True
    return e, s


def _create_user(email, password_hash, full_name, phone, request):
    """Create the account — or claim the password-less one guest checkout made for
    this e-mail, so the orders already placed against it stay in the same history.

    The ON CONFLICT guard is what makes that safe: it only overwrites a row with no
    password. A real account's row can't be taken over by re-registering its e-mail,
    and two simultaneous claims can't both win.
    """
    user = fetch_one(
        """insert into users (email, password_hash, full_name, phone)
                values (%s, %s, %s, %s)
           on conflict (email) do update
                  set password_hash = excluded.password_hash,
                      full_name = coalesce(nullif(excluded.full_name, ''), users.full_name),
                      phone = coalesce(nullif(excluded.phone, ''), users.phone)
                where coalesce(users.password_hash, '') = ''
           returning id, email, full_name, phone, role""",
        [email, password_hash, full_name, phone],
    )
    if not user:   # the row exists and already has a password — nothing to claim
        raise HTTPException(409, "This email is already registered")
    log_action(user_id=user["id"], action="register", request=request)
    return {"verified": True, "token": sign_token(user), "user": public_user(user)}


def _send_codes(email, phone, email_code, phone_code):
    """Send both codes (best-effort). In non-prod, unsent codes are printed so the
    flow is testable without real providers; returns (email_sent, sms_sent)."""
    subject = "رمز التحقق — دكّان كنعان"
    body = (f"مرحباً،\n\nرمز التحقق الخاص بك في دكّان كنعان هو: {email_code}\n"
            f"الرمز صالحٌ لمدة {VERIFY_TTL_MIN} دقائق.\n\nإن لم تطلب هذا الرمز فتجاهل هذه الرسالة.")
    email_sent = send_email(email, subject, body)
    sms_sent = send_sms(phone, f"دكّان كنعان: رمز التحقق {phone_code} (صالح {VERIFY_TTL_MIN} دقائق)")
    if not _IS_PROD:  # never echo real codes into production logs
        if not email_sent:
            print(f"[verify] EMAIL code for {email}: {email_code}")
        if not sms_sent:
            print(f"[verify] SMS code for {phone}: {phone_code}")
    return email_sent, sms_sent


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
    # An account created by guest checkout has no password yet: that e-mail may
    # still register — doing so claims the row (see _create_user).
    if fetch_one("select 1 from users where email = %s and coalesce(password_hash, '') <> ''", [email]):
        raise HTTPException(409, "This email is already registered")

    pw_hash = hash_password(password)
    email_req, phone_req = _required_channels()
    if not email_req and not phone_req:
        # no verification channel available → create the account directly (a broken
        # or unconfigured provider must never block sales)
        return _create_user(email, pw_hash, payload.get("full_name"), phone_norm, request)

    ec, pc = _code(), _code()
    # A signup already under way for this address is LEFT ALONE: whoever started
    # first keeps a working code. Verification is looked up by row id, so several
    # attempts can be live at once, and whichever code gets entered decides which
    # attempt — and so which password — wins.
    #
    # Only attempts that have already expired are cleared, and only for this same
    # address. That keeps the table from growing forever without any sweep that could
    # reach a live signup.
    execute("delete from signup_verifications where lower(email) = %s and expires_at < now()", [email])
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
        if not resp["email_sent"] and not _IS_PROD:
            print(f"[verify] EMAIL code for {email}: {ec}")
        dev["email"] = ec
    if phone_req:
        resp["phone_sent"] = send_sms(phone_norm, f"دكّان كنعان: رمز التحقق {pc} (صالح {VERIFY_TTL_MIN} دقائق)")
        if not resp["phone_sent"] and not _IS_PROD:
            print(f"[verify] SMS code for {phone_norm}: {pc}")
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
        log_action(action="verify_failed", detail={"email": v["email"], "reason": "too_many"}, request=request)
        raise HTTPException(429, "Too many attempts — please start again")
    execute("update signup_verifications set attempts = attempts + 1 where id = %s", [vid])

    email_ok = v["email_ok"] or (bool(ec) and ec == v["email_code"])
    phone_ok = v["phone_ok"] or (bool(pc) and pc == v["phone_code"])
    execute("update signup_verifications set email_ok = %s, phone_ok = %s where id = %s",
            [email_ok, phone_ok, vid])
    if not (email_ok and phone_ok):
        # A signup stalls here more than anywhere else — a code that never arrived,
        # or the wrong one typed. Which channel failed is the useful part.
        log_action(action="verify_failed",
                   detail={"email": v["email"], "email_ok": email_ok, "phone_ok": phone_ok,
                           "attempt": v["attempts"] + 1}, request=request)
        return {"verified": False, "email_ok": email_ok, "phone_ok": phone_ok}

    # One creation path for both flows (this one and the no-verification-channel
    # shortcut in register_start), so claiming a guest account works in both.
    #
    # The pending row is only discarded once it can serve no further purpose: the
    # account now exists, or the e-mail already has one. If creation fails for any
    # other reason — the database blinking, say — the row stays, so the customer can
    # submit the same code again instead of starting the whole signup over.
    try:
        result = _create_user(v["email"], v["password_hash"], v["full_name"], v["phone"], request)
    except HTTPException:
        execute("delete from signup_verifications where id = %s", [vid])
        raise
    execute("delete from signup_verifications where id = %s", [vid])
    return result


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
        # Recorded so the dashboard can show who is locked out. `known` separates a
        # customer mistyping their own password from an address with no account.
        log_action(user_id=(user or {}).get("id"), action="login_failed",
                   detail={"email": email, "known": bool(user)}, request=request)
        raise HTTPException(401, "Invalid login credentials")
    log_action(user_id=user["id"], action="login", request=request)
    return {"token": sign_token(user), "user": public_user(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    row = fetch_one("select id, email, full_name, phone, role from users where id = %s", [user["id"]])
    if not row:
        raise HTTPException(404, "User not found")
    return {"user": row}


# PATCH /api/auth/me — let a signed-in customer edit their own name/phone.
# Email is intentionally NOT editable: it's verified at signup and is the login
# identity, so changing it would need a fresh verification flow.
@router.patch("/me")
def update_me(user=Depends(current_user), payload: dict = Body(default={})):
    fields, values = [], []
    if "full_name" in payload:
        fields.append("full_name = %s")
        values.append((payload.get("full_name") or "").strip() or None)
    if "phone" in payload:
        phone = normalize_uae_phone(payload.get("phone"))
        if not phone:
            raise HTTPException(400, "Invalid UAE phone number")
        fields.append("phone = %s")
        values.append(phone)
    if not fields:
        raise HTTPException(400, "Nothing to update")
    row = fetch_one(
        f"update users set {', '.join(fields)} where id = %s returning id, email, full_name, phone, role",
        values + [user["id"]],
    )
    if not row:
        raise HTTPException(404, "User not found")
    return {"user": row}
