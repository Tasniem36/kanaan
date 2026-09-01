"""Failure signals, and the follow-up list built from them.

The log used to record only successes, so a customer could try six times and give up
without leaving a trace. These tests pin down that each dead-end is written, that the
storefront can't invent its own actions, and that the follow-up list is manager-only.
"""
import pytest

import routers.audit as A
import routers.auth as auth
import routers.orders as orders


# --- the storefront's one way into the log ------------------------------------
def test_only_whitelisted_client_events_are_accepted(client, monkeypatch):
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    assert client.post("/api/audit/event", json={"event": "checkout_opened"}).json() == {"ok": True}
    assert logged and logged[0]["action"] == "checkout_opened"
    logged.clear()
    for bogus in ["order_placed", "login", "", "'; drop table audit_logs; --"]:
        assert client.post("/api/audit/event", json={"event": bogus}).json() == {"ok": False}
    assert logged == [], "a page must not be able to write arbitrary actions"


def test_a_client_event_keeps_only_the_fields_we_expect(client, monkeypatch):
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    client.post("/api/audit/event", json={
        "event": "checkout_opened",
        "detail": {"items": 3, "total": 180, "user_id": "someone-else", "note": "x" * 9999}})
    assert logged[0]["detail"] == {"items": 3, "total": 180}


def test_client_events_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(A, "log_action", lambda **k: None)
    codes = {client.post("/api/audit/event", json={"event": "checkout_opened"}).status_code
             for _ in range(40)}
    assert 429 in codes


# --- the failures themselves ---------------------------------------------------
def test_a_failed_sign_in_is_recorded(client, monkeypatch):
    logged = []
    monkeypatch.setattr(auth, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None: None)   # no such account
    assert client.post("/api/auth/login", json={"email": "who@example.com", "password": "Abcdef12"}).status_code == 401
    assert logged[0]["action"] == "login_failed"
    assert logged[0]["detail"]["known"] is False, "an unknown e-mail is a different problem"


def test_a_wrong_password_is_marked_as_a_known_account(client, monkeypatch):
    logged = []
    monkeypatch.setattr(auth, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(auth, "fetch_one",
                        lambda sql, params=None: {"id": "u1", "password_hash": "not-a-match", "role": "customer"})
    monkeypatch.setattr(auth, "verify_password", lambda pw, h: False)
    client.post("/api/auth/login", json={"email": "known@example.com", "password": "Wrong123"})
    assert logged[0]["detail"] == {"email": "known@example.com", "known": True}


def test_a_stalled_signup_records_which_channel_failed(client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    logged = []
    monkeypatch.setattr(auth, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(auth, "execute", lambda *a, **k: None)
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None: {
        "id": "v1", "email": "x@example.com", "phone": "+971500000000", "full_name": "n",
        "password_hash": "h", "email_code": "111111", "phone_code": "222222",
        "email_ok": False, "phone_ok": False, "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)})
    res = client.post("/api/auth/register/verify",
                      json={"verification_id": "v1", "email_code": "111111", "phone_code": "999999"})
    assert res.json()["verified"] is False
    assert logged[0]["action"] == "verify_failed"
    assert logged[0]["detail"]["email_ok"] is True and logged[0]["detail"]["phone_ok"] is False


def test_a_rejected_promo_code_is_recorded(client, as_user, monkeypatch):
    import routers.discounts as disc
    logged = []
    monkeypatch.setattr(disc, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(disc, "evaluate_code", lambda *a, **k: {"error": "This code has expired"})
    as_user({"id": "me", "role": "customer"})
    assert client.post("/api/discounts/validate", json={"code": "RAMADAN", "subtotal": 200}).status_code == 400
    assert logged[0]["action"] == "promo_invalid"
    assert logged[0]["detail"]["code"] == "RAMADAN"


def test_the_checkout_dead_ends_are_recorded(client, as_user, monkeypatch):
    logged = []
    monkeypatch.setattr(orders, "log_action", lambda **k: logged.append(k))
    as_user({"id": "me", "role": "customer"})
    base = {"customer_name": "تسنيم", "phone": "0501234567", "city": "دبي",
            "street": "ش", "house": "1", "items": [{"product_id": "x", "qty": 1}]}
    client.post("/api/orders", json={**base, "house": ""})       # a field left blank
    client.post("/api/orders", json={**base, "phone": "12345"})  # not a UAE mobile
    assert [l["action"] for l in logged] == ["checkout_failed", "checkout_failed"]
    assert [l["detail"]["reason"] for l in logged] == ["missing_fields", "bad_phone"]


# --- the follow-up list --------------------------------------------------------
def test_the_follow_up_list_is_manager_only(client):
    from conftest import token_for
    assert client.get("/api/audit/struggling").status_code == 401
    shopper = {"Authorization": f"Bearer {token_for('me', 'customer')}"}
    assert client.get("/api/audit/struggling", headers=shopper).status_code == 403
    assert client.get("/api/audit/sources").status_code == 401


def test_the_follow_up_window_is_bounded(client, monkeypatch):
    """An unbounded window would scan the whole table."""
    from conftest import token_for
    seen = []
    monkeypatch.setattr(A, "fetch_all", lambda sql, params=None: seen.append(params) or [{"opened": 0, "ordered": 0}])
    headers = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    client.get("/api/audit/struggling?hours=999999", headers=headers)
    assert seen[0][0] == 24 * 30, "clamped to a month"
    client.get("/api/audit/struggling?hours=nonsense", headers=headers)
    assert seen[-1][0] == 24, "falls back to a day"


def test_the_struggle_actions_are_defined_in_one_place():
    """The list drives both the follow-up query and the dashboard's red pills."""
    assert set(A.STRUGGLE_ACTIONS) == {
        "login_failed", "verify_failed", "password_reset_failed", "promo_invalid",
        "checkout_failed", "out_of_stock", "checkout_login_required",
        "track_lookup_failed"}


# --- the interest trail ------------------------------------------------------
def test_the_basket_and_the_search_box_can_report_themselves(client, monkeypatch):
    """Neither is visible to the server: a basket lives in the browser until checkout,
    and a search looks exactly like browsing the catalogue."""
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    client.post("/api/audit/event", json={
        "event": "cart_add", "detail": {"product_id": "p1", "name": "زعتر", "qty": 2}})
    client.post("/api/audit/event", json={
        "event": "search", "detail": {"q": "  زيت   زيتون ", "results": 0}})
    assert [l["action"] for l in logged] == ["cart_add", "search"]
    assert logged[0]["detail"] == {"product_id": "p1", "name": "زعتر", "qty": 2}
    assert logged[1]["detail"] == {"q": "زيت زيتون", "results": 0}, "whitespace collapsed"


def test_each_product_and_each_term_keeps_its_own_row(client, monkeypatch):
    """Collapsing per visitor would hide the one thing these rows are for: which
    products, and which words."""
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    client.post("/api/audit/event", json={"event": "cart_add", "detail": {"product_id": "p1"}})
    client.post("/api/audit/event", json={"event": "cart_add", "detail": {"product_id": "p2"}})
    client.post("/api/audit/event", json={"event": "search", "detail": {"q": "زعتر"}})
    assert [l["dedupe"] for l in logged] == ["p1", "p2", "زعتر"]


def test_a_page_still_cannot_invent_an_event_or_a_field(client, monkeypatch):
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    assert client.post("/api/audit/event", json={"event": "order_placed"}).json() == {"ok": False}
    client.post("/api/audit/event", json={
        "event": "cart_add", "detail": {"product_id": "p1", "price": 0.01, "admin": True}})
    assert logged[0]["detail"] == {"product_id": "p1"}, "only the whitelisted fields survive"


def test_a_long_search_term_is_trimmed_before_it_is_stored(client, monkeypatch):
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    client.post("/api/audit/event", json={"event": "search", "detail": {"q": "x" * 500}})
    assert len(logged[0]["detail"]["q"]) == 80


def test_being_sent_to_sign_in_at_the_checkout_is_recorded(client, monkeypatch):
    """The storefront redirects before any endpoint is reached, so without this the
    shop's own sign-in wall is the one drop-off it can't see."""
    logged = []
    monkeypatch.setattr(A, "log_action", lambda **k: logged.append(k))
    client.post("/api/audit/event", json={
        "event": "checkout_login_required", "detail": {"items": 3, "total": 180}})
    assert logged[0]["action"] == "checkout_login_required"
    assert logged[0]["detail"] == {"items": 3, "total": 180}
    assert "checkout_login_required" in A.STRUGGLE_ACTIONS, "a wall, not a browse"


def test_saving_a_product_is_recorded(client, as_user, monkeypatch):
    import routers.wishlist as w
    logged = []
    monkeypatch.setattr(w, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(w, "fetch_one", lambda sql, params=None: {"name": "إبريق"})
    monkeypatch.setattr(w, "execute", lambda *a, **k: None)
    as_user({"id": "me", "role": "customer"})
    client.put("/api/wishlist/p1")
    assert logged[0]["action"] == "wishlist_add"
    assert logged[0]["detail"]["name"] == "إبريق" and logged[0]["dedupe"] == "p1"


def test_asking_to_be_told_when_something_is_back_is_recorded(client, as_user, monkeypatch):
    """A sale lost for want of stock, with someone's name on it — which is what makes
    a restock worth ordering."""
    import routers.products as pr
    logged = []
    monkeypatch.setattr(pr, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(pr, "fetch_one", lambda sql, params=None: {"id": "p1", "name": "لبنة", "stock": 0})
    monkeypatch.setattr(pr, "execute", lambda *a, **k: None)
    as_user({"id": "me", "role": "customer"})
    client.post("/api/products/p1/stock-alert")
    assert logged[0]["action"] == "stock_alert" and logged[0]["detail"]["name"] == "لبنة"


def test_a_customer_who_cannot_find_their_order_is_recorded(client, monkeypatch):
    logged = []
    monkeypatch.setattr(orders, "log_action", lambda **k: logged.append(k))
    monkeypatch.setattr(orders, "fetch_one", lambda sql, params=None: None)
    res = client.post("/api/orders/lookup", json={"ref": "DK-ABC1234", "contact": "0501234567"})
    assert res.status_code == 404
    assert logged[0]["action"] == "track_lookup_failed"
    assert logged[0]["detail"]["ref"] == "ABC1234", "normalised, as the lookup saw it"


def test_a_busy_basket_cannot_spend_the_checkout_events_budget(client, monkeypatch):
    """One shared allowance would let a shopper adding items exhaust it and lose their
    own checkout_opened — silently understating the drop-off figure."""
    monkeypatch.setattr(A, "log_action", lambda **k: None)
    for _ in range(40):
        client.post("/api/audit/event", json={"event": "cart_add", "detail": {"product_id": "p1"}})
    res = client.post("/api/audit/event", json={"event": "checkout_opened", "detail": {"items": 1}})
    assert res.status_code == 200, "the one event that feeds the funnel must still get through"
