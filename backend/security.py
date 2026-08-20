"""Password hashing (bcrypt, compatible with the old bcryptjs hashes),
JWT issuing/verifying, and FastAPI auth dependencies."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request

from db import fetch_one

SECRET = os.getenv("JWT_SECRET", "")
EXPIRES_HOURS = 24

# A weak/missing signing key lets anyone forge a manager token. Refuse to start
# rather than silently fall back to a guessable secret. Local dev sets JWT_SECRET
# in backend/.env (see .env.example); allow a short one only outside production.
_IS_PROD = os.getenv("ENV", "").lower() in ("prod", "production")
if not SECRET or SECRET == "dev-secret-change-me":
    raise RuntimeError("JWT_SECRET is not set — refusing to start with a guessable signing key")
if _IS_PROD and len(SECRET) < 32:
    raise RuntimeError("JWT_SECRET is too short for production (use a 64-char random string)")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def sign_token(user) -> str:
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        # The generation of sign-ins this token belongs to. Callers pass the row they
        # just read; a caller that forgets is caught immediately, because a token
        # stamped with the wrong number is refused on the very next request.
        "v": user.get("token_version", 0),
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRES_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _is_retired(payload) -> bool:
    """True when this token belongs to a generation of sign-ins that has been closed.

    Changing a password signs out every other device (see routers/auth.py), and a JWT
    is self-contained — nothing in it can be withdrawn — so the only thing that can
    retire one early is a counter kept beside the account. Checking it costs one
    primary-key read per authenticated request, which is what buys the guarantee.

    A token issued before the column existed carries no number and matches the 0
    every account starts at, so the deploy that adds this signs nobody out.
    """
    row = fetch_one("select token_version from users where id = %s", [payload["sub"]])
    if not row:
        return True   # the account is gone; its tokens go with it
    return int(payload.get("v", 0)) != row["token_version"]


def _user_from_request(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], SECRET, algorithms=["HS256"])
    except Exception:
        return None
    if _is_retired(payload):
        return None
    return {"id": payload["sub"], "role": payload.get("role")}


# --- dependencies ---
def optional_user(request: Request):
    return _user_from_request(request)


def current_user(request: Request):
    u = _user_from_request(request)
    if not u:
        raise HTTPException(status_code=401, detail="Authentication required")
    return u


def require_manager(request: Request):
    u = current_user(request)
    if u["role"] != "manager":
        raise HTTPException(status_code=403, detail="Manager access required")
    return u
