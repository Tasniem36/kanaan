from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from psycopg import errors as pg_errors

from db import fetch_one
from security import hash_password, verify_password, sign_token, current_user
from validate import is_email, is_strong_password, normalize_uae_phone
from audit import log_action

router = APIRouter()


def public_user(u):
    return {"id": u["id"], "email": u["email"], "full_name": u["full_name"], "phone": u["phone"], "role": u["role"]}


@router.post("/register")
def register(request: Request, response: Response, payload: dict = Body(default={})):
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "البريد وكلمة المرور مطلوبان")
    if not is_email(email):
        raise HTTPException(400, "بريد إلكتروني غير صالح")
    phone_norm = normalize_uae_phone(payload.get("phone"))
    if not phone_norm:
        raise HTTPException(400, "رقم هاتفٍ إماراتيٍّ غير صالح")
    if not is_strong_password(password):
        raise HTTPException(400, "كلمة المرور ضعيفة: ٨ أحرفٍ على الأقل مع حرفٍ كبيرٍ وصغيرٍ ورقم")
    try:
        user = fetch_one(
            """insert into users (email, password_hash, full_name, phone)
               values (%s, %s, %s, %s) returning id, email, full_name, phone, role""",
            [email.lower(), hash_password(password), payload.get("full_name"), phone_norm],
        )
    except pg_errors.UniqueViolation:
        raise HTTPException(409, "هذا البريد مسجّلٌ مسبقًا")
    log_action(user_id=user["id"], action="register", request=request)
    response.status_code = 201
    return {"token": sign_token(user), "user": public_user(user)}


@router.post("/login")
def login(request: Request, payload: dict = Body(default={})):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "البريد وكلمة المرور مطلوبان")
    user = fetch_one("select * from users where email = %s", [email])
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "بيانات الدخول غير صحيحة")
    log_action(user_id=user["id"], action="login", request=request)
    return {"token": sign_token(user), "user": public_user(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    row = fetch_one("select id, email, full_name, phone, role from users where id = %s", [user["id"]])
    if not row:
        raise HTTPException(404, "المستخدم غير موجود")
    return {"user": row}
