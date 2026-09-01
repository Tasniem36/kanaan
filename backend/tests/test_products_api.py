"""Product listing contract: filters, the sort whitelist, and paging.

The DB is patched out (see conftest), so these assert on the SQL we *build* and
the shape we return — not on query results. SQL that must actually execute
correctly is covered in test_db_integration.py.
"""
import pytest

import routers.products as products_mod
from conftest import token_for


@pytest.fixture
def captured(monkeypatch):
    """Record the SQL/params list_products builds, and return canned rows."""
    calls = []

    def fake_fetch_all(sql, params=None):
        calls.append((" ".join(sql.split()), list(params or [])))
        return [
            {"id": "p1", "name": "زيت", "price": 55, "stock": 3, "total_count": 7},
            {"id": "p2", "name": "زعتر", "price": 20, "stock": 0, "total_count": 7},
        ]

    monkeypatch.setattr(products_mod, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(products_mod, "log_action", lambda **k: None)
    return calls


def test_total_comes_from_the_window_count(client, captured):
    r = client.get("/api/products?active=1")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 7, "total should be the window count, not len(rows)"
    assert len(body["products"]) == 2


def test_total_count_is_stripped_from_every_row(client, captured):
    """It's an implementation detail of the one-query count; leaking it would put
    a bogus field on every product in the client's catalog."""
    rows = client.get("/api/products?active=1").json()["products"]
    assert rows, "fixture should return rows"
    for row in rows:
        assert "total_count" not in row


def test_empty_result_reports_zero_total(client, monkeypatch):
    monkeypatch.setattr(products_mod, "fetch_all", lambda sql, params=None: [])
    monkeypatch.setattr(products_mod, "log_action", lambda **k: None)
    body = client.get("/api/products?active=1").json()
    assert body == {"products": [], "total": 0}


# --- sort whitelist ---------------------------------------------------------
@pytest.mark.parametrize("key,expected", [
    ("featured", "sort, created_at"),
    ("newest", "created_at desc"),
    # an item on offer belongs where its offer price puts it, not its old one
    ("price_asc", "coalesce(sale_price, price), sort"),
    ("price_desc", "coalesce(sale_price, price) desc, sort"),
    ("name", "name"),
])
def test_each_sort_option_maps_to_its_clause(client, captured, key, expected):
    client.get(f"/api/products?active=1&sort={key}")
    sql, _ = captured[-1]
    assert f"order by stock = 0, {expected}" in sql


@pytest.mark.parametrize("evil", [
    "'; drop table users; --",
    "price; delete from orders",
    "(select 1)",
    "unknown_column",
    "",
])
def test_unknown_sort_falls_back_and_never_reaches_the_sql(client, captured, evil):
    """The sort key is interpolated into ORDER BY, so it must come from the
    whitelist only — a raw client string there would be SQL injection."""
    client.get("/api/products", params={"active": "1", "sort": evil})
    sql, _ = captured[-1]
    assert sql.endswith("order by stock = 0, sort, created_at")
    assert evil.strip() == "" or evil not in sql


# --- price filter -----------------------------------------------------------
def test_price_bounds_are_passed_as_parameters(client, captured):
    client.get("/api/products?active=1&min_price=10&max_price=99.5")
    sql, params = captured[-1]
    assert "coalesce(sale_price, price) >= %s" in sql
    assert "coalesce(sale_price, price) <= %s" in sql, "a bound is on what's paid, not the old price"
    assert 10.0 in params and 99.5 in params


@pytest.mark.parametrize("bad", ["abc", "", "-5", "NaN "])
def test_unparseable_or_negative_price_bounds_are_ignored(client, captured, bad):
    client.get("/api/products", params={"active": "1", "min_price": bad})
    sql, _ = captured[-1]
    assert "price >=" not in sql, f"{bad!r} should not have produced a bound"


def test_price_zero_is_a_real_bound_not_falsy(client, captured):
    """0 is a legitimate minimum and must not be dropped as falsy."""
    client.get("/api/products?active=1&min_price=0")
    sql, params = captured[-1]
    assert "coalesce(sale_price, price) >= %s" in sql and 0.0 in params


# --- search -----------------------------------------------------------------
def test_search_covers_both_languages(client, captured):
    client.get("/api/products?active=1&q=olive")
    sql, params = captured[-1]
    for col in ("name ilike", "name_en, '') ilike", "description, '') ilike", "description_en, '') ilike"):
        assert col in sql, f"missing {col}"
    assert params.count("%olive%") == 4


def test_search_term_is_parameterised_not_interpolated(client, captured):
    client.get("/api/products", params={"active": "1", "q": "100%' or 1=1 --"})
    sql, params = captured[-1]
    assert "or 1=1" not in sql
    assert "%100%' or 1=1 --%" in params


# --- storefront vs manager ordering ----------------------------------------
def test_storefront_sinks_sold_out_items(client, captured):
    client.get("/api/products?active=1&sort=price_asc")
    sql, _ = captured[-1]
    assert "order by stock = 0, coalesce(sale_price, price), sort" in sql


def test_manager_inventory_keeps_its_configured_order(client, captured, monkeypatch):
    """A manager managing stock needs to see sold-out rows in place, not pushed
    to the bottom of the list."""
    monkeypatch.setattr(products_mod, "optional_user", lambda r: {"id": "m", "role": "manager"})
    client.get("/api/products?sort=price_asc")
    sql, _ = captured[-1]
    assert "order by coalesce(sale_price, price), sort" in sql
    assert "stock = 0" not in sql


def test_storefront_forces_active_only_even_for_a_manager(client, captured, monkeypatch):
    monkeypatch.setattr(products_mod, "optional_user", lambda r: {"id": "m", "role": "manager"})
    client.get("/api/products?active=1")
    sql, _ = captured[-1]
    assert "is_active = true" in sql


# --- paging -----------------------------------------------------------------
def test_limit_and_offset_are_applied(client, captured):
    client.get("/api/products?active=1&limit=8&offset=16")
    sql, params = captured[-1]
    assert sql.endswith("limit %s offset %s")
    assert params[-2:] == [8, 16]


def test_negative_offset_is_clamped_to_zero(client, captured):
    client.get("/api/products?active=1&limit=8&offset=-40")
    _, params = captured[-1]
    assert params[-1] == 0


def test_garbage_paging_values_do_not_500(client, captured):
    assert client.get("/api/products?active=1&limit=abc").status_code == 200
    assert client.get("/api/products?active=1&limit=8&offset=xyz").status_code == 200


# --- stock alerts -----------------------------------------------------------
def test_stock_alert_requires_sign_in(client):
    assert client.post("/api/products/p1/stock-alert").status_code == 401
    assert client.get("/api/products/p1/stock-alert").status_code == 401


def test_stock_alert_on_unknown_product_is_404(client, as_user, monkeypatch):
    monkeypatch.setattr(products_mod, "fetch_one", lambda sql, params=None: None)
    as_user({"id": "u1", "role": "shopper"})
    assert client.post("/api/products/nope/stock-alert").status_code == 404


def test_stock_alert_refused_when_already_in_stock(client, as_user, monkeypatch):
    """Nothing to wait for — and subscribing would never fire."""
    monkeypatch.setattr(products_mod, "fetch_one", lambda sql, params=None: {"id": "p1", "stock": 4})
    monkeypatch.setattr(products_mod, "execute",
                        lambda *a, **k: pytest.fail("should not have subscribed"))
    as_user({"id": "u1", "role": "shopper"})
    assert client.post("/api/products/p1/stock-alert").status_code == 400


def test_stock_alert_is_recorded_for_a_sold_out_product(client, as_user, monkeypatch):
    seen = []
    monkeypatch.setattr(products_mod, "fetch_one",
                        lambda sql, params=None: {"id": "p1", "name": "لبنة", "stock": 0})
    monkeypatch.setattr(products_mod, "execute", lambda sql, params=None: seen.append(params))
    monkeypatch.setattr(products_mod, "log_action", lambda **k: None)
    as_user({"id": "u1", "role": "shopper"})
    r = client.post("/api/products/p1/stock-alert")
    assert r.status_code == 200 and r.json() == {"subscribed": True}
    assert seen == [["u1", "p1"]]


# --- write access -----------------------------------------------------------
@pytest.mark.parametrize("method,path", [
    ("post", "/api/products"),
    ("patch", "/api/products/p1"),
    ("delete", "/api/products/p1"),
    ("post", "/api/products/p1/restock"),
])
def test_catalog_writes_are_manager_only(client, method, path):
    """require_manager resolves the token itself, so an anonymous or shopper
    caller must be turned away before any DB work happens."""
    send = getattr(client, method)
    kw = {} if method == "delete" else {"json": {}}
    assert send(path, **kw).status_code == 401, "anonymous must be rejected"

    shopper = {"Authorization": f"Bearer {token_for('u1', 'shopper')}"}
    assert send(path, headers=shopper, **kw).status_code == 403, "a shopper must be forbidden"
