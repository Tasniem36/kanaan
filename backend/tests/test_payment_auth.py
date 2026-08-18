"""Regression tests for the payment-endpoint access control fix.

confirm-payment / cancel-payment used to be unauthenticated and unscoped: anyone
who learned an order's UUID could confirm or cancel it. They now require a logged-in
caller who owns the order (or a manager).
"""
import routers.orders as orders_mod

# A real UUID: the endpoints reject a malformed order id up front (404), so a
# placeholder like "order-123" would never reach the ownership check under test.
ORDER_ID = "0f1d4e0e-2222-4000-8000-000000000000"


def _order(user_id="owner", **over):
    o = {
        "id": ORDER_ID,
        "user_id": user_id,
        "payment_status": "pending",
        "payment_method": "ziina",
        "ziina_payment_id": "pi_1",
        "status": "pending",
        "total": 100,
    }
    o.update(over)
    return o


# --- unauthenticated callers are rejected -----------------------------------
def test_confirm_payment_requires_auth(client):
    r = client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert r.status_code == 401


def test_cancel_payment_requires_auth(client):
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.status_code == 401


# --- a logged-in user cannot touch someone else's order ---------------------
def test_confirm_payment_rejects_non_owner(client, as_user, monkeypatch):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(user_id="someone-else"))
    # network/DB must never be reached once ownership fails:
    monkeypatch.setattr(orders_mod, "get_payment_intent", lambda pid: (_ for _ in ()).throw(AssertionError("should not verify")))
    as_user({"id": "attacker", "role": "shopper"})
    r = client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert r.status_code == 404  # 404 not 403: don't confirm the order exists


def test_cancel_payment_rejects_non_owner(client, as_user, monkeypatch):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(user_id="someone-else"))
    monkeypatch.setattr(orders_mod, "cancel_and_restore", lambda oid: (_ for _ in ()).throw(AssertionError("should not cancel")))
    as_user({"id": "attacker", "role": "shopper"})
    r = client.post(f"/api/orders/{ORDER_ID}/cancel-payment")
    assert r.status_code == 404


# --- the rightful owner still gets through ----------------------------------
def test_owner_can_confirm(client, as_user, monkeypatch):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(user_id="owner"))
    monkeypatch.setattr(orders_mod, "get_payment_intent", lambda pid: {"status": "pending"})
    as_user({"id": "owner", "role": "shopper"})
    r = client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert r.status_code == 200
    assert r.json() == {"paid": False, "status": "pending"}


# --- a manager may act on any order -----------------------------------------
def test_manager_can_confirm_any_order(client, as_user, monkeypatch):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(user_id="someone-else"))
    monkeypatch.setattr(orders_mod, "get_payment_intent", lambda pid: {"status": "pending"})
    as_user({"id": "the-manager", "role": "manager"})
    r = client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert r.status_code == 200
    assert r.json()["paid"] is False
