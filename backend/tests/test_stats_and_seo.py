"""Manager dashboard access control, and the sitemap's output.

The dashboard exposes revenue and customer counts, so the access check is the
part that matters most here. The revenue *arithmetic* needs a real database and
lives in test_db_integration.py.
"""
import pytest

import routers.stats as stats
import routers.seo as seo
from conftest import token_for


# --- dashboard is manager-only ----------------------------------------------
def test_overview_rejects_anonymous(client):
    assert client.get("/api/stats/overview").status_code == 401


def test_overview_rejects_a_shopper(client, monkeypatch):
    """Revenue and customer totals must not leak to a signed-in customer."""
    monkeypatch.setattr(stats, "fetch_one", lambda *a, **k: pytest.fail("should not query"))
    monkeypatch.setattr(stats, "fetch_all", lambda *a, **k: pytest.fail("should not query"))
    r = client.get("/api/stats/overview",
                   headers={"Authorization": f"Bearer {token_for('u1', 'shopper')}"})
    assert r.status_code == 403


def test_overview_returns_the_whole_dashboard_in_one_response(client, monkeypatch):
    """The page makes a single request, so every section must be present."""
    monkeypatch.setattr(stats, "fetch_one", lambda sql, params=None: {"revenue_today": 0})
    monkeypatch.setattr(stats, "fetch_all", lambda sql, params=None: [])
    r = client.get("/api/stats/overview",
                   headers={"Authorization": f"Bearer {token_for('m', 'manager')}"})
    assert r.status_code == 200
    body = r.json()
    for key in ("money", "by_status", "customers", "top_products", "low_stock", "daily"):
        assert key in body, f"dashboard section {key!r} missing"
    assert body["low_stock_threshold"] == stats.LOW_STOCK_THRESHOLD


def test_revenue_definition_excludes_cancelled_and_abandoned_payments():
    """A cancelled order isn't income, and neither is a Ziina checkout the customer
    never completed. Guards the shared REAL_ORDER predicate."""
    assert "status <> 'cancelled'" in stats.REAL_ORDER
    assert "payment_status = 'paid'" in stats.REAL_ORDER
    assert "not hidden" in stats.REAL_ORDER


def test_days_are_bucketed_in_the_shops_timezone():
    """UTC bucketing would roll "today" over at 4am local time."""
    assert stats.TZ == "Asia/Dubai"


# --- sitemap ----------------------------------------------------------------
class _Req:
    def __init__(self, host="dukkan-kanaan.com", proto="https"):
        self.headers = {"host": host, "x-forwarded-proto": proto}
        self.url = type("U", (), {"scheme": "http", "netloc": host})()


@pytest.fixture
def products(monkeypatch):
    def _set(rows):
        monkeypatch.setattr(seo, "fetch_all", lambda sql, params=None: rows)
    return _set


def _xml(**kw):
    return seo.sitemap(_Req(**kw)).body.decode()


def test_sitemap_is_public(client, monkeypatch):
    """Crawlers are anonymous — and it must not sit under /api, where the
    no-store middleware would strip its cache headers."""
    monkeypatch.setattr(seo, "fetch_all", lambda sql, params=None: [])
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert "max-age" in r.headers.get("cache-control", "")


def test_sitemap_lists_products_and_category_pages(products):
    import datetime
    products([{"id": "p1", "lastmod": datetime.datetime(2026, 3, 4)}])
    xml = _xml()
    assert "<loc>https://dukkan-kanaan.com/product/p1</loc>" in xml
    assert "/category/pantry" in xml and "/category/pottery" in xml
    assert "<lastmod>2026-03-04</lastmod>" in xml


def test_sitemap_omits_private_and_pointless_pages(products):
    """Sign-in, account, dashboard and payment-return URLs have nothing to index."""
    products([])
    xml = _xml()
    for path in ("/login", "/register", "/account", "/manager", "/pay"):
        assert path not in xml, f"{path} should not be in the sitemap"


def test_sitemap_honours_the_forwarded_scheme(products, monkeypatch):
    """Behind Caddy/nginx the app sees http; the public URL is https."""
    monkeypatch.delenv("APP_URL", raising=False)
    products([])
    assert "https://dukkan-kanaan.com/" in _xml(proto="https")


def test_sitemap_prefers_configured_app_url(products, monkeypatch):
    monkeypatch.setenv("APP_URL", "https://dukkan-kanaan.com/")
    products([])
    xml = _xml(host="internal-lb:8080", proto="http")
    assert "internal-lb" not in xml, "a proxy host must not leak into the sitemap"
    assert "https://dukkan-kanaan.com/category/pantry" in xml


def test_sitemap_is_well_formed_and_escapes_ids(products, monkeypatch):
    """A stray & in a URL would make the whole document unparseable."""
    import xml.etree.ElementTree as ET
    monkeypatch.delenv("APP_URL", raising=False)
    products([{"id": "a&b<c", "lastmod": None}])
    doc = _xml()
    assert "&amp;" in doc
    root = ET.fromstring(doc)  # raises if malformed
    assert root.tag.endswith("urlset")
