"""Password hashing (bcrypt, compatible with the old bcryptjs hashes),
JWT issuing/verifying, and FastAPI auth dependencies."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
EXPIRES_HOURS = 24


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
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRES_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _user_from_request(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:], SECRET, algorithms=["HS256"])
        return {"id": payload["sub"], "role": payload.get("role")}
    except Exception:
        return None


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
