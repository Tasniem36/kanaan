"""What the return URL is allowed to conclude about the money.

Landing on /pay/return?cancel=1 says which URL Ziina redirected to, not what happened
to the payment: failure_url is the same URL, and a customer can pay and then press
cancel or back. cancel-payment used to treat anything short of "completed" — including
a Ziina it could not reach — as permission to cancel the order and put the stock back.
Nothing ever revisits such an order (there is no webhook), so a payment that settled a
moment later was lost silently.

These tests pin the rule: destroy an order only on an answer that says the money is
definitely not coming.
"""
import pytest
from fastapi import HTTPException

import routers.orders as orders_mod

ORDER_ID = "0f1d4e0e-2222-4000-8000-000000000000"


def _order(**over):
    o = {
        "id": ORDER_ID,
        "user_id": "owner",
        "payment_status": "pending",
        "payment_method": "ziina",
        "ziina_payment_id": "pi_1",
        "status": "pending",
        "total": 100,
    }
    o.update(over)
    return o


@pytest.fixture
def owner(as_user):
    as_user({"id": "owner", "role": "shopper"})


@pytest.fixture
def settled(monkeypatch):
    """Record what the endpoint decided, without touching a database."""
    calls = {"cancelled": [], "paid": []}
    monkeypatch.setattr(orders_mod, "cancel_and_restore", lambda oid: calls["cancelled"].append(oid))
    monkeypatch.setattr(orders_mod, "mark_paid", lambda order, request=None: calls["paid"].append(str(order["id"])))
    return calls


def _intent(status):
    return lambda pid: {"status": status}


def _unreachable(pid):
    raise HTTPException(502, "Could not verify the payment")


# --- an unresolved payment is never cancelled -------------------------------
@pytest.mark.parametrize("status", ["pending", "requires_payment_instrument", "something_new"])
def test_cancel_leaves_an_unresolved_payment_alone(client, owner, monkeypatch, settled, status):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order())
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent(status))
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.json() == {"cancelled": False, "paid": False, "pending": True}
    assert settled["cancelled"] == []  # the stock stays reserved for the sweep


def test_cancel_leaves_the_order_alone_when_ziina_cannot_be_asked(client, owner, monkeypatch, settled):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order())
    monkeypatch.setattr(orders_mod, "get_payment_intent", _unreachable)
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.status_code == 200
    assert r.json()["pending"] is True
    assert settled["cancelled"] == []  # a network blip is not an answer about the money


# --- an answer, either way, is acted on -------------------------------------
def test_cancel_settles_a_payment_that_had_already_completed(client, owner, monkeypatch, settled):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order())
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent("completed"))
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.json() == {"cancelled": False, "paid": True}
    assert settled["paid"] == [ORDER_ID]
    assert settled["cancelled"] == []


@pytest.mark.parametrize("status", ["failed", "cancelled", "canceled", "expired"])
def test_cancel_restores_stock_when_the_money_is_definitely_not_coming(
        client, owner, monkeypatch, settled, status):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order())
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent(status))
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.json() == {"cancelled": True}
    assert settled["cancelled"] == [ORDER_ID]


def test_cancel_of_a_cash_order_needs_no_payment_lookup(client, owner, monkeypatch, settled):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(payment_method="cod", ziina_payment_id=None))
    monkeypatch.setattr(orders_mod, "get_payment_intent", lambda pid: pytest.fail("no Ziina intent to ask about"))
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.json() == {"cancelled": True}
    assert settled["cancelled"] == [ORDER_ID]


# --- an order cancelled before the money landed comes back with its stock ----
def test_confirming_a_cancelled_order_takes_its_stock_back_off_the_shelf(client, owner, monkeypatch):
    taken = []
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(status="cancelled"))
    monkeypatch.setattr(orders_mod, "fetch_all", lambda sql, params=None: [])
    monkeypatch.setattr(orders_mod, "execute", lambda sql, params=None: None)
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent("completed"))
    monkeypatch.setattr(orders_mod, "reserve_stock", lambda oid: taken.append(oid))
    monkeypatch.setattr(orders_mod, "notify_new_order", lambda order: None)
    monkeypatch.setattr(orders_mod, "_notify_new_order_admins", lambda order: None)
    monkeypatch.setattr(orders_mod, "_send_order_whatsapp", lambda order, request: None)
    monkeypatch.setattr(orders_mod, "log_action", lambda **k: None)
    r = client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert r.json() == {"paid": True, "status": "paid"}
    # cancel_and_restore had put these units back; the payment makes the order real
    # again, so they leave the shelf a second time or the shop oversells them
    assert taken == [ORDER_ID]


def test_confirming_a_live_order_does_not_double_deduct(client, owner, monkeypatch):
    taken = []
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order())
    monkeypatch.setattr(orders_mod, "fetch_all", lambda sql, params=None: [])
    monkeypatch.setattr(orders_mod, "execute", lambda sql, params=None: None)
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent("completed"))
    monkeypatch.setattr(orders_mod, "reserve_stock", lambda oid: taken.append(oid))
    monkeypatch.setattr(orders_mod, "notify_new_order", lambda order: None)
    monkeypatch.setattr(orders_mod, "_notify_new_order_admins", lambda order: None)
    monkeypatch.setattr(orders_mod, "_send_order_whatsapp", lambda order, request: None)
    monkeypatch.setattr(orders_mod, "log_action", lambda **k: None)
    client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert taken == []  # its stock was taken at checkout and never given back
