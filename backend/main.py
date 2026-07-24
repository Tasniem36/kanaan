import datetime
import decimal
import json
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def _json_default(o):
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    raise TypeError(f"not serializable: {type(o).__name__}")


class SafeJSONResponse(JSONResponse):
    """Serializes Decimal / datetime / UUID (which the DB returns) and keeps Arabic readable."""
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, default=_json_default).encode("utf-8")

from routers.auth import router as auth_router
from routers.products import router as products_router
from routers.orders import router as orders_router
from routers.addresses import router as addresses_router
from routers.users import router as users_router
from routers.discounts import router as discounts_router
from routers.audit import router as audit_router
from routers.content import router as content_router

app = FastAPI(
    title="Dukkan Kanaan API",
    version="1.0.0",
    default_response_class=SafeJSONResponse,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

_origins = os.getenv("CORS_ORIGIN", "").split(",") if os.getenv("CORS_ORIGIN") else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])


# never let the browser cache API responses/redirects (avoids stale 308s etc.)
@app.middleware("http")
async def no_store(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# match the Node error shape the frontend reads: { "error": "..." }
@app.exception_handler(StarletteHTTPException)
async def _http_error(_request, exc):
    detail = exc.detail if exc.detail and exc.detail != "Not Found" else "المسار غير موجود"
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def _validation_error(_request, _exc):
    return JSONResponse(status_code=400, content={"error": "طلبٌ غير صالح"})


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(auth_router, prefix="/api/auth")
app.include_router(products_router, prefix="/api/products")
app.include_router(orders_router, prefix="/api/orders")
app.include_router(addresses_router, prefix="/api/addresses")
app.include_router(users_router, prefix="/api/users")
app.include_router(discounts_router, prefix="/api/discounts")
app.include_router(audit_router, prefix="/api/audit")
app.include_router(content_router, prefix="/api/content")
