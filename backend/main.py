import datetime
import decimal
import json
import os
import secrets
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
from routers.reviews import router as reviews_router
from routers.settings import router as settings_router
from routers.inbox import notif_router, msg_router
from routers.push import router as push_router
from routers.errors import router as errors_router
from routers.cart import router as cart_router
from routers.wishlist import router as wishlist_router
from routers.stats import router as stats_router
from routers.seo import router as seo_router

_IS_PROD = os.getenv("ENV", "").lower() in ("prod", "production")

app = FastAPI(
    title="Dukkan Kanaan API",
    version="1.0.0",
    default_response_class=SafeJSONResponse,
    # Don't expose the interactive API explorer / schema in production.
    docs_url=None if _IS_PROD else "/api/docs",
    redoc_url=None if _IS_PROD else "/api/redoc",
    openapi_url=None if _IS_PROD else "/api/openapi.json",
)

# The SPA is served same-origin (nginx proxies /api), so cross-origin access is
# not needed. Only allow the origins explicitly listed in CORS_ORIGIN; default
# to none rather than "*" so a missing env var can't open the API to any site.
_origins = [o.strip() for o in os.getenv("CORS_ORIGIN", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])


# An anonymous id per browser, used only to tell visitors apart in the activity log
# and the dashboard's counts. First-party, no third party ever sees it, and it holds
# nothing about the person — a random 32 hex characters. Guests were counted by IP
# before, which made everyone behind one wifi look like a single visitor.
VISITOR_COOKIE = "vid"
_VISITOR_MAX_AGE = 60 * 60 * 24 * 365


def _valid_vid(v):
    return isinstance(v, str) and len(v) == 32 and all(c in "0123456789abcdef" for c in v)


@app.middleware("http")
async def visitor_cookie(request: Request, call_next):
    existing = request.cookies.get(VISITOR_COOKIE)
    issued = None if _valid_vid(existing) else secrets.token_hex(16)
    # audit.py reads this off the request; it never trusts the raw cookie value
    request.state.visitor = existing if issued is None else issued
    response = await call_next(request)
    if issued:
        response.set_cookie(
            VISITOR_COOKIE, issued, max_age=_VISITOR_MAX_AGE, path="/",
            httponly=True,          # only the server reads it; no script needs it
            samesite="lax",
            secure=_IS_PROD,
        )
    return response


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
    detail = exc.detail if exc.detail and exc.detail != "Not Found" else "Not found"
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def _validation_error(_request, _exc):
    return JSONResponse(status_code=400, content={"error": "Invalid request"})


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
app.include_router(reviews_router, prefix="/api/reviews")
app.include_router(settings_router, prefix="/api/settings")
app.include_router(notif_router, prefix="/api/notifications")
app.include_router(msg_router, prefix="/api/messages")
app.include_router(push_router, prefix="/api/push")
app.include_router(errors_router, prefix="/api/errors")
app.include_router(cart_router, prefix="/api/cart")
app.include_router(wishlist_router, prefix="/api/wishlist")
app.include_router(stats_router, prefix="/api/stats")
# Mounted at the root, NOT under /api: crawlers expect /sitemap.xml, and the
# no-store middleware above would strip its cache headers.
app.include_router(seo_router)

# Serve stored product images at /media/... (nginx proxies /media/ here in prod).
from fastapi.staticfiles import StaticFiles  # noqa: E402
_media_dir = os.getenv("MEDIA_DIR", "/app/media")
os.makedirs(_media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")
