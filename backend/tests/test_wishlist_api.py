"""Saved products: access control and the add/remove contract.

A wishlist is per-customer data, so the interesting risk is one account reading
or mutating another's — every endpoint must be scoped to the caller's own id.
"""
import pytest

import routers.wishlist as wl


@pytest.fixture
def spy(monkeypatch):
    """Capture the SQL/params the endpoints issue."""
    calls = []
    monkeypatch.setattr(wl, "execute", lambda sql, params=None: calls.append((" ".join(sql.split()), list(params or []))))
    monkeypatch.setattr(wl, "fetch_all", lambda sql, params=None: (
        calls.append((" ".join(sql.split()), list(params or []))) or
        [{"id": "p1", "name": "زيت", "name_en": "Olive oil"}]
    ))
    # the row the handler reads to check the product exists, and to name it in the log
    monkeypatch.setattr(wl, "fetch_one", lambda sql, params=None: {"x": 1, "name": "زيت"})
    monkeypatch.setattr(wl, "log_action", lambda **k: None)
    return calls


# --- every endpoint requires a session --------------------------------------
@pytest.mark.parametrize("method,path", [
    ("get", "/api/wishlist"),
    ("get", "/api/wishlist/ids"),
    ("put", "/api/wishlist/p1"),
    ("delete", "/api/wishlist/p1"),
])
def test_wishlist_requires_sign_in(client, method, path):
    assert getattr(client, method)(path).status_code == 401


# --- reads are scoped to the caller -----------------------------------------
def test_list_only_selects_the_callers_own_rows(client, as_user, spy):
    as_user({"id": "me", "role": "shopper"})
    assert client.get("/api/wishlist").status_code == 200
    sql, params = spy[-1]
    assert "w.user_id = %s" in sql
    assert params == ["me"], "must filter by the caller, not a client-supplied id"


def test_list_hides_products_that_were_deactivated(client, as_user, spy):
    """A saved product the manager has since hidden must not resurface."""
    as_user({"id": "me", "role": "shopper"})
    client.get("/api/wishlist")
    sql, _ = spy[-1]
    assert "p.is_active = true" in sql


def test_ids_endpoint_is_scoped_and_returns_plain_ids(client, as_user, monkeypatch):
    seen = {}

    def fake(sql, params=None):
        seen["params"] = list(params or [])
        return [{"product_id": "p1"}, {"product_id": "p2"}]

    monkeypatch.setattr(wl, "fetch_all", fake)
    as_user({"id": "me", "role": "shopper"})
    r = client.get("/api/wishlist/ids")
    assert r.json() == {"ids": ["p1", "p2"]}
    assert seen["params"] == ["me"]


# --- writes ------------------------------------------------------------------
def test_saving_an_unknown_product_is_404(client, as_user, monkeypatch):
    monkeypatch.setattr(wl, "fetch_one", lambda sql, params=None: None)
    monkeypatch.setattr(wl, "execute", lambda *a, **k: pytest.fail("should not insert"))
    as_user({"id": "me", "role": "shopper"})
    assert client.put("/api/wishlist/nope").status_code == 404


def test_saving_twice_is_idempotent(client, as_user, spy):
    """The heart can be double-tapped; a duplicate must not 500 on the PK."""
    as_user({"id": "me", "role": "shopper"})
    assert client.put("/api/wishlist/p1").status_code == 200
    sql, params = spy[-1]
    assert "on conflict (user_id, product_id) do nothing" in sql
    assert params == ["me", "p1"]


def test_removing_is_scoped_to_the_caller(client, as_user, spy):
    """Without the user_id predicate this would delete other people's rows."""
    as_user({"id": "me", "role": "shopper"})
    r = client.delete("/api/wishlist/p1")
    assert r.status_code == 204
    sql, params = spy[-1]
    assert "where user_id = %s and product_id = %s" in sql
    assert params == ["me", "p1"]


def test_removing_something_not_saved_is_still_204(client, as_user, spy):
    """Idempotent delete — the client's optimistic UI shouldn't see an error."""
    as_user({"id": "me", "role": "shopper"})
    assert client.delete("/api/wishlist/never-saved").status_code == 204
