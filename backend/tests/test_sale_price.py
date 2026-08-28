"""A product on offer: it keeps its usual price and gains a sale price, which is
what it actually sells for while the offer runs.

The two prices only mean anything against each other, so most of what matters here
is the pair staying coherent — and the shopper being charged the offer, not the
price they can see crossed out.
"""
import pytest
from fastapi import HTTPException

import routers.products as products


# --- the pair has to make sense ---------------------------------------------
def test_an_offer_is_the_price_below_the_usual_one():
    assert products._sale_price(30, 50) == 30.0
    assert products._sale_price("30.50", 50) == 30.5


def test_no_offer_is_a_perfectly_good_answer():
    assert products._sale_price(None, 50) is None
    assert products._sale_price("", 50) is None, "a cleared field ends the offer"


def test_an_offer_at_or_above_the_usual_price_is_refused():
    """The crossed-out price beside it would be a lie, which is the one thing a
    shopper is entitled to trust about a sale."""
    for bad in (50, 60):
        with pytest.raises(HTTPException) as e:
            products._sale_price(bad, 50)
        assert e.value.status_code == 400
        assert "below the usual price" in e.value.detail


def test_a_free_or_negative_offer_is_refused():
    for bad in (0, -5):
        with pytest.raises(HTTPException):
            products._sale_price(bad, 50)


def test_a_nonsense_offer_is_a_400_not_a_500():
    with pytest.raises(HTTPException) as e:
        products._sale_price("abc", 50)
    assert e.value.status_code == 400


# --- editing an existing product --------------------------------------------
def _patch(client, monkeypatch, current, payload):
    """PATCH a product whose stored row is `current`; returns the written columns."""
    from conftest import token_for
    written = {}

    def fetch_one(sql, params=None):
        if sql.strip().startswith("select price"):
            return current
        written["sql"], written["params"] = " ".join(sql.split()), params
        return {"id": "p1", "stock": 1, "prev_stock": 1}

    monkeypatch.setattr(products, "fetch_one", fetch_one)
    monkeypatch.setattr(products, "notify_users", lambda **k: None)
    return written, client.patch("/api/products/p1", json=payload,
                                 headers={"Authorization": f"Bearer {token_for('boss', 'manager')}"})


def test_starting_an_offer_on_an_existing_product(client, monkeypatch):
    written, res = _patch(client, monkeypatch, {"price": 50, "sale_price": None}, {"sale_price": 40})
    assert res.status_code == 200
    assert "sale_price = %s" in written["sql"] and 40.0 in written["params"]


def test_ending_an_offer_clears_it(client, monkeypatch):
    written, res = _patch(client, monkeypatch, {"price": 50, "sale_price": 40}, {"sale_price": ""})
    assert res.status_code == 200
    assert None in written["params"]


def test_dropping_the_usual_price_under_a_running_offer_is_refused(client, monkeypatch):
    """The edit that reads as innocent: only `price` is sent, and it lands at or below
    a sale that's already running. Checked as the row will end up, not as it arrives."""
    _, res = _patch(client, monkeypatch, {"price": 50, "sale_price": 40}, {"price": 35})
    assert res.status_code == 400
    assert "below the usual price" in res.json()["error"]


def test_raising_the_usual_price_over_a_running_offer_is_fine(client, monkeypatch):
    _, res = _patch(client, monkeypatch, {"price": 50, "sale_price": 40}, {"price": 60})
    assert res.status_code == 200


def test_both_can_move_together(client, monkeypatch):
    written, res = _patch(client, monkeypatch, {"price": 50, "sale_price": 40},
                          {"price": 30, "sale_price": 25})
    assert res.status_code == 200
    assert 25.0 in written["params"] and 30 in written["params"]


def test_an_edit_that_touches_neither_price_reads_nothing_extra(client, monkeypatch):
    """The pair is only re-checked when one of them moves."""
    from conftest import token_for
    seen = []

    def fetch_one(sql, params=None):
        seen.append(" ".join(sql.split()))
        return {"id": "p1", "stock": 1, "prev_stock": 1}

    monkeypatch.setattr(products, "fetch_one", fetch_one)
    monkeypatch.setattr(products, "notify_users", lambda **k: None)
    res = client.patch("/api/products/p1", json={"stock": 4},
                       headers={"Authorization": f"Bearer {token_for('boss', 'manager')}"})
    assert res.status_code == 200
    assert not any(s.startswith("select price") for s in seen)


# --- what the storefront is told ---------------------------------------------
def test_the_storefront_sorts_and_filters_on_what_is_actually_paid():
    """An item on offer belongs where its offer price puts it, not where its old one
    would — otherwise "cheapest first" lists it above things that cost more."""
    assert products.SORT_SQL["price_asc"].startswith("coalesce(sale_price, price)")
    assert products.SORT_SQL["price_desc"].startswith("coalesce(sale_price, price) desc")


def test_every_product_payload_carries_the_offer(client, monkeypatch):
    """A page that gets `price` without `sale_price` would show the old price as if it
    were the one being asked for."""
    seen = []
    monkeypatch.setattr(products, "fetch_all", lambda sql, params=None: seen.append(sql) or [])
    client.get("/api/products?limit=5")
    client.get("/api/products/p1/related")
    assert seen and all("sale_price" in s for s in seen)
