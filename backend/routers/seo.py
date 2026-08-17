"""sitemap.xml, generated from the live catalogue.

Products come and go, so a file baked at build time would go stale the first time
the manager adds something. nginx maps /sitemap.xml here (see frontend/nginx.conf).
"""
import os
from xml.sax.saxutils import escape

from fastapi import APIRouter, Request, Response

from db import fetch_all

router = APIRouter()

# Pages worth indexing that aren't products. Sign-in/checkout/account are
# excluded on purpose — see frontend/public/robots.txt.
STATIC_PATHS = [("/", "daily", "1.0"), ("/category/pantry", "daily", "0.9"), ("/category/pottery", "daily", "0.9")]


def _origin(request: Request) -> str:
    """Public site origin, without a trailing slash."""
    configured = os.getenv("APP_URL", "").strip().rstrip("/")
    if configured:
        return configured
    # behind nginx/Caddy the original scheme arrives in X-Forwarded-Proto
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{proto}://{host}"


def _url(loc: str, lastmod=None, changefreq=None, priority=None) -> str:
    parts = [f"<loc>{escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"<lastmod>{lastmod.date().isoformat()}</lastmod>")
    if changefreq:
        parts.append(f"<changefreq>{changefreq}</changefreq>")
    if priority:
        parts.append(f"<priority>{priority}</priority>")
    return "<url>" + "".join(parts) + "</url>"


@router.get("/sitemap.xml")
def sitemap(request: Request):
    base = _origin(request)
    products = fetch_all(
        """select id, greatest(created_at, coalesce(updated_at, created_at)) as lastmod
           from products where is_active = true order by created_at desc limit 5000"""
    )
    urls = [_url(f"{base}{path}", changefreq=freq, priority=pri) for path, freq, pri in STATIC_PATHS]
    urls += [_url(f"{base}/product/{p['id']}", lastmod=p["lastmod"], changefreq="weekly", priority="0.8")
             for p in products]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(urls) + "</urlset>")
    # a crawler re-fetch every few hours is plenty; this is a full table read
    return Response(xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})
