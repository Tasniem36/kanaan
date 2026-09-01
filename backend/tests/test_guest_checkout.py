"""Checkout without an account, and the tracking link that replaces an order history.

The risks worth pinning down:
  * a guest order must still capture the delivery details and a usable e-mail;
  * the tracking token must be the *only* way in without a session, and must not
    let one order's link open another's;
  * registering later must be able to claim the account guest checkout created —
    but must never take over an account that already has a password.
"""
import pytest

import routers.orders as orders
import routers.auth as auth


GUEST = {"customer_name": "تسنيم", "phone": "0501234567", "city": "دبي",
         "street": "شارع", "house": "12", "email": "guest@example.com",
         "items": [{"product_id": "6f1d4e0e-0000-4000-8000-000000000000", "qty": 1}]}


@pytest.fixture
def stub_order(monkeypatch):
    """Stand in for the whole transactional body of create_order, capturing what
    SQL it ran so the guest-account path can be asserted on."""
    calls = []
    state = {"order": None}

    class FakeCur:
        description = True

        def execute(self, sql, params=None):
            calls.append((" ".join(str(sql).split()), list(params or [])))

        def fetchall(self):
            sql = calls[-1][0]
            if "from users where email" in sql:
                return []                      # no existing account for this e-mail
            if "insert into users" in sql:
                return [{"id": "new-user", "email": GUEST["email"], "full_name": "تسنيم",
                         "phone": "+971501234567", "role": "customer"}]
            if "from products" in sql:
                return [{"id": GUEST["items"][0]["product_id"], "name": "زيت", "price": 65, "stock": 5}]
            if "insert into orders" in sql:
                state["order"] = {
                    "id": "0f1d4e0e-1111-4000-8000-000000000000", "user_id": "new-user",
                    "customer_name": "تسنيم", "phone": "+971501234567", "total": 90,
                    "payment_method": "cod", "status": "pending", "track_token": "tok-abc",
                }
                return [state["order"]]
            return []

    class FakeConn:
        def cursor(self): return _ctx(FakeCur())
        def transaction(self): return _ctx(None)

    class _ctx:
        def __init__(self, v): self.v = v
        def __enter__(self): return self.v
        def __exit__(self, *a): return False

    monkeypatch.setattr(orders, "pool", type("P", (), {"connection": staticmethod(lambda: _ctx(FakeConn()))})())
    monkeypatch.setattr(orders, "execute", lambda *a, **k: None)
    monkeypatch.setattr(orders, "log_action", lambda **k: None)
    monkeypatch.setattr(orders, "notify_new_order", lambda *a, **k: None)
    monkeypatch.setattr(orders, "_notify_new_order_admins", lambda *a, **k: None)
    monkeypatch.setattr(orders, "compute_delivery_fee", lambda city, total: 25)
    # the manager switch — on for these tests; the gate itself is covered below
    monkeypatch.setattr(orders, "get_checkout_config", lambda: {"guest_allowed": True})
    sent = []
    monkeypatch.setattr(orders, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return calls, sent, state


# --- placing an order without a session --------------------------------------
def test_a_guest_can_place_an_order(client, stub_order):
    calls, _, state = stub_order
    res = client.post("/api/orders", json=GUEST)
    assert res.status_code == 200, res.text
    assert state["order"], "the order row was never written"


def test_a_guest_order_gets_an_account_for_its_e_mail(client, stub_order):
    calls, _, _ = stub_order
    client.post("/api/orders", json=GUEST)
    inserted = [c for c in calls if "insert into users" in c[0]]
    assert inserted, "no account was created for the guest"
    sql, params = inserted[0]
    assert "values (%s, '', %s, %s)" in sql, "the guest account must have an empty password_hash"
    assert params[0] == GUEST["email"]


def test_the_order_carries_a_tracking_token_and_a_short_number(client, stub_order):
    calls, _, _ = stub_order
    client.post("/api/orders", json=GUEST)
    sql, params = next(c for c in calls if "insert into orders" in c[0])
    assert "track_token, ref" in sql
    token, ref = params[-2], params[-1]
    assert len(token) > 16, "the token is the credential, so it must not be guessable"
    assert len(ref) == 7, "the number is read out loud and typed, so it stays short"


def test_the_guest_is_e_mailed_the_tracking_link(client, stub_order):
    _, sent, _ = stub_order
    client.post("/api/orders", json=GUEST)
    assert sent, "no confirmation e-mail"
    to, _subject, body = sent[0]
    assert to == GUEST["email"]
    assert "/track/0f1d4e0e-1111-4000-8000-000000000000?t=tok-abc" in body


@pytest.mark.parametrize("missing", ["customer_name", "phone", "city", "street", "house"])
def test_the_delivery_details_are_still_required(client, stub_order, missing):
    assert client.post("/api/orders", json={**GUEST, missing: ""}).status_code == 400


@pytest.mark.parametrize("email", ["not-an-email", "a@b"])
def test_a_guest_who_gives_an_e_mail_must_give_a_usable_one(client, stub_order, email):
    """Optional, but a typo is caught rather than silently swallowed — the customer
    would otherwise wait for a confirmation that could never arrive."""
    assert client.post("/api/orders", json={**GUEST, "email": email}).status_code == 400


@pytest.mark.parametrize("email", ["", "   ", None])
def test_a_guest_needs_no_e_mail_at_all(client, stub_order, email):
    """The phone is what the shop delivers to and calls, and the order carries it — so
    an order can be found by number + phone with no account and no address."""
    body = {**GUEST}
    if email is None:
        body.pop("email")
    else:
        body["email"] = email
    assert client.post("/api/orders", json=body).status_code == 200


def test_an_order_with_no_e_mail_hangs_off_no_account(client, stub_order):
    """There is nothing to key an account on and nothing to send to it, so the order
    stands alone rather than creating a row with a made-up address on it."""
    calls, _sent, _state = stub_order
    body = {k: v for k, v in GUEST.items() if k != "email"}
    client.post("/api/orders", json=body)
    inserted = next(p for sql, p in calls if sql.startswith("insert into orders"))
    assert inserted[0] is None, "user_id"
    assert not any(sql.startswith("insert into users") for sql, _ in calls)


def test_a_signed_in_customer_needs_no_e_mail(client, app, stub_order):
    from security import optional_user
    app.dependency_overrides[optional_user] = lambda: {"id": "me", "role": "customer"}
    body = {k: v for k, v in GUEST.items() if k != "email"}
    assert client.post("/api/orders", json=body).status_code == 200


# --- the tracking link -------------------------------------------------------
@pytest.fixture
def one_order(monkeypatch):
    row = {"id": "0f1d4e0e-1111-4000-8000-000000000000", "user_id": "someone-else",
           "customer_name": "تسنيم", "phone": "+971501234567", "city": "دبي", "street": "ش",
           "house": "12", "notes": None, "status": "preparing", "total": 90,
           "payment_method": "cod", "payment_status": "unpaid", "delivery_fee": 25,
           "discount_amount": 0, "leave_at_door": False, "door_note": None,
           "created_at": "2026-08-18T10:00:00Z", "track_token": "tok-abc"}
    monkeypatch.setattr(orders, "fetch_one", lambda sql, params=None: dict(row))
    monkeypatch.setattr(orders, "fetch_all", lambda sql, params=None: [])
    monkeypatch.setattr(orders, "cancel_and_restore", lambda oid: None)  # no live pool in tests
    return row


OID = "0f1d4e0e-1111-4000-8000-000000000000"


def test_the_right_token_opens_the_order(client, one_order):
    res = client.get(f"/api/orders/track/{OID}?t=tok-abc")
    assert res.status_code == 200
    o = res.json()["order"]
    assert o["status"] == "preparing" and o["items"] == [] and o["events"] == []


@pytest.mark.parametrize("qs", ["", "?t=", "?t=wrong", "?t=tok-ab"])
def test_no_token_or_a_wrong_one_is_a_404(client, one_order, qs):
    """404 rather than 403 — a guessed order id shouldn't confirm the order exists."""
    assert client.get(f"/api/orders/track/{OID}{qs}").status_code == 404


def test_the_tracking_page_hides_the_full_phone_and_the_account(client, one_order):
    o = client.get(f"/api/orders/track/{OID}?t=tok-abc").json()["order"]
    assert "user_id" not in o and "track_token" not in o and "phone" not in o
    assert o["phone_hint"] == "+971*****4567"


def test_a_malformed_order_id_is_a_404(client, one_order):
    assert client.get("/api/orders/track/not-a-uuid?t=tok-abc").status_code == 404


def test_a_guest_can_settle_their_own_payment_with_the_token(client, one_order):
    """Coming back from Ziina there's no session, so the token has to be enough."""
    assert client.post(f"/api/orders/{OID}/cancel-payment?t=tok-abc").status_code != 401
    assert client.post(f"/api/orders/{OID}/cancel-payment?t=nope").status_code == 404


# --- claiming the account later ----------------------------------------------
def test_register_treats_an_unclaimed_guest_account_as_available(client, monkeypatch):
    """The e-mail exists but has no password, so registering must proceed, not 409."""
    seen = {}

    def fake_fetch_one(sql, params=None):
        flat = " ".join(sql.split())
        if "from users where email" in flat:
            seen["guard"] = flat
            return None          # the guard excludes password-less rows
        if "insert into signup_verifications" in flat:
            return {"id": "v-1"}
        return None

    monkeypatch.setattr(auth, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(auth, "execute", lambda *a, **k: None)
    monkeypatch.setattr(auth, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(auth, "send_sms", lambda *a, **k: True)
    res = client.post("/api/auth/register", json={
        "email": "guest@example.com", "password": "Abcdef12", "phone": "0501234567"})
    assert res.status_code == 200, res.text
    assert "coalesce(password_hash, '') <> ''" in seen["guard"], \
        "the duplicate-e-mail guard must ignore accounts that have no password yet"


def test_claiming_only_overwrites_a_password_less_row(client, monkeypatch):
    """A real account must not be hijacked by re-registering its e-mail."""
    captured = {}

    def fake_fetch_one(sql, params=None):
        flat = " ".join(sql.split())
        if "insert into users" in flat:
            captured["sql"] = flat
            return None          # ON CONFLICT ... WHERE matched nothing → has a password
        return None

    monkeypatch.setattr(auth, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(auth, "log_action", lambda **k: None)
    with pytest.raises(Exception) as e:
        auth._create_user("taken@example.com", "hash", "n", "+971500000000", None)
    assert "already registered" in str(e.value)
    assert "where coalesce(users.password_hash, '') = ''" in captured["sql"]


def test_the_verify_step_claims_through_the_same_creation_path(client, monkeypatch):
    """Regression: register_verify used to run its own INSERT, so it hit the unique
    constraint and 409'd on a guest account instead of claiming it. Both register
    paths must go through _create_user, which is where the claim lives."""
    from datetime import datetime, timedelta, timezone
    pending = {
        "id": "v-1", "email": "guest@example.com", "phone": "+971501234567",
        "full_name": "زائر", "password_hash": "new-hash", "email_code": "111111",
        "phone_code": "222222", "email_ok": False, "phone_ok": False, "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    called = {}
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None: dict(pending))
    monkeypatch.setattr(auth, "execute", lambda *a, **k: None)
    def fake_create_user(*args, **kwargs):
        called["args"] = args
        return {"verified": True, "token": "t", "user": {"id": "same-row"}}

    monkeypatch.setattr(auth, "_create_user", fake_create_user)
    res = client.post("/api/auth/register/verify", json={
        "verification_id": "v-1", "email_code": "111111", "phone_code": "222222"})
    assert res.status_code == 200, res.text
    assert called.get("args"), "verify must delegate to _create_user, not INSERT on its own"
    assert called["args"][0] == "guest@example.com"


def test_an_empty_password_hash_can_never_log_in():
    """The guest account's stored hash is '' — bcrypt must reject every attempt."""
    from security import verify_password
    for attempt in ["", " ", "Abcdef12", "x" * 72]:
        assert verify_password(attempt, "") is False

# --- the manager's guest-checkout switch -------------------------------------
def test_guest_ordering_is_refused_unless_the_manager_allows_it(client, stub_order, monkeypatch):
    """Off by default: a guest gets 401 so the storefront sends them to sign in."""
    monkeypatch.setattr(orders, "get_checkout_config", lambda: {"guest_allowed": False})
    assert client.post("/api/orders", json=GUEST).status_code == 401


def test_the_switch_defaults_to_closed(monkeypatch):
    """A missing settings row must read as 'not allowed', not as 'allowed'."""
    import routers.settings as settings_mod
    monkeypatch.setattr(settings_mod, "fetch_one", lambda sql, params=None: None)
    assert settings_mod.get_checkout_config()["guest_allowed"] is False
    monkeypatch.setattr(settings_mod, "fetch_one", lambda sql, params=None: {"value": {}})
    assert settings_mod.get_checkout_config()["guest_allowed"] is False
    monkeypatch.setattr(settings_mod, "fetch_one", lambda sql, params=None: {"value": {"guest_allowed": True}})
    assert settings_mod.get_checkout_config()["guest_allowed"] is True


def test_a_signed_in_customer_is_unaffected_by_the_switch(client, app, stub_order, monkeypatch):
    monkeypatch.setattr(orders, "get_checkout_config", lambda: {"guest_allowed": False})
    from security import optional_user
    app.dependency_overrides[optional_user] = lambda: {"id": "me", "role": "customer"}
    body = {k: v for k, v in GUEST.items() if k != "email"}
    assert client.post("/api/orders", json=body).status_code == 200


def test_only_a_manager_may_flip_the_switch(client, monkeypatch):
    from conftest import token_for
    monkeypatch.setattr("routers.settings.fetch_one", lambda sql, params=None: {"key": "checkout"})
    assert client.patch("/api/settings/checkout", json={"guest_allowed": True}).status_code == 401
    shopper = {"Authorization": f"Bearer {token_for('me', 'customer')}"}
    assert client.patch("/api/settings/checkout", json={"guest_allowed": True}, headers=shopper).status_code == 403
    mgr = {"Authorization": f"Bearer {token_for('boss', 'manager')}"}
    res = client.patch("/api/settings/checkout", json={"guest_allowed": "yes"}, headers=mgr)
    assert res.status_code == 200 and res.json()["checkout"] == {"guest_allowed": True}


# --- finding an order without the e-mailed link ------------------------------
@pytest.fixture
def lookup_row(monkeypatch):
    row = {"id": OID, "phone": "+971501234567", "track_token": "tok-abc", "email": "guest@example.com"}
    monkeypatch.setattr(orders, "fetch_one", lambda sql, params=None: dict(row))
    return row


@pytest.mark.parametrize("contact", ["0501234567", "+971501234567", "971501234567",
                                     "guest@example.com", "GUEST@example.com"])
def test_the_order_number_plus_a_matching_contact_finds_it(client, lookup_row, contact):
    """The phone in any local format, or the e-mail — whichever they remember."""
    res = client.post("/api/orders/lookup", json={"ref": "DK-K7M2XPQ", "contact": contact})
    assert res.status_code == 200, res.text
    assert res.json() == {"id": OID, "token": "tok-abc"}


@pytest.mark.parametrize("contact", ["0509999999", "someone@else.com", "x"])
def test_the_number_alone_is_not_enough(client, lookup_row, contact):
    """It's short and printed on paper, so it must be paired with something known."""
    assert client.post("/api/orders/lookup", json={"ref": "DK-K7M2XPQ", "contact": contact}).status_code == 404


def test_a_wrong_number_and_a_wrong_contact_look_identical(client, monkeypatch):
    """Same 404 either way, so the endpoint can't be used to discover live numbers."""
    monkeypatch.setattr(orders, "fetch_one", lambda sql, params=None: None)
    missing = client.post("/api/orders/lookup", json={"ref": "DK-NOSUCH", "contact": "0501234567"})
    assert missing.status_code == 404
    monkeypatch.setattr(orders, "fetch_one", lambda sql, params=None: {
        "id": OID, "phone": "+971501234567", "track_token": "tok-abc", "email": "a@b.com"})
    mismatch = client.post("/api/orders/lookup", json={"ref": "DK-K7M2XPQ", "contact": "0509999999"})
    assert mismatch.status_code == 404
    assert missing.json() == mismatch.json()


def test_the_number_is_accepted_however_it_is_typed(client, lookup_row, monkeypatch):
    seen = {}

    def fake(sql, params=None):
        seen["ref"] = (params or [None])[0]
        return dict(lookup_row)

    monkeypatch.setattr(orders, "fetch_one", fake)
    for typed in ["DK-K7M2XPQ", "dk-k7m2xpq", "K7M2XPQ", " k7m2xpq ", "#K7M2XPQ"]:
        client.post("/api/orders/lookup", json={"ref": typed, "contact": "0501234567"})
        assert seen["ref"] == "K7M2XPQ", f"{typed!r} normalised to {seen['ref']!r}"


def test_lookup_needs_both_fields(client, lookup_row):
    assert client.post("/api/orders/lookup", json={"ref": "DK-K7M2XPQ"}).status_code == 400
    assert client.post("/api/orders/lookup", json={"contact": "0501234567"}).status_code == 400


def test_lookup_is_rate_limited(client, lookup_row):
    """Guessing pairs has to be expensive."""
    codes = [client.post("/api/orders/lookup", json={"ref": "DK-XXXXXXX", "contact": "0509999999"}).status_code
             for _ in range(14)]
    assert 429 in codes, "no rate limit on the lookup"


def test_order_numbers_avoid_ambiguous_characters():
    """A number read out over the phone shouldn't hinge on 0-vs-O or 1-vs-I."""
    seen = set()
    for _ in range(200):
        ref = orders.new_ref(lambda r: False)
        assert len(ref) == 7
        seen.update(ref)
    assert not (seen & set("01IO")), f"ambiguous characters in use: {seen & set('01IO')}"


def test_a_transient_failure_keeps_the_pending_signup(client, monkeypatch):
    """If account creation fails for an unexpected reason, the customer must be able
    to submit the same code again rather than start the whole signup over."""
    from datetime import datetime, timedelta, timezone
    deleted = []
    pending = {
        "id": "v-1", "email": "x@example.com", "phone": "+971500000000", "full_name": "n",
        "password_hash": "h", "email_code": "111111", "phone_code": "222222",
        "email_ok": True, "phone_ok": True, "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None: dict(pending))
    monkeypatch.setattr(auth, "execute",
                        lambda sql, params=None: deleted.append(params) if "delete" in sql else None)
    monkeypatch.setattr(auth, "_create_user",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("database blinked")))
    with pytest.raises(RuntimeError):
        client.post("/api/auth/register/verify",
                    json={"verification_id": "v-1", "email_code": "111111", "phone_code": "222222"})
    assert deleted == [], "the pending signup must survive so the code still works"


def test_a_taken_email_does_discard_the_pending_signup(client, monkeypatch):
    """That one can never complete, and the row holds a password hash."""
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException
    deleted = []
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None: {
        "id": "v-1", "email": "taken@example.com", "phone": "+971500000000", "full_name": "n",
        "password_hash": "h", "email_code": "111111", "phone_code": "222222",
        "email_ok": True, "phone_ok": True, "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)})
    monkeypatch.setattr(auth, "execute",
                        lambda sql, params=None: deleted.append(params) if "delete" in sql else None)
    monkeypatch.setattr(auth, "_create_user",
                        lambda *a, **k: (_ for _ in ()).throw(HTTPException(409, "This email is already registered")))
    assert client.post("/api/auth/register/verify",
                       json={"verification_id": "v-1", "email_code": "111111",
                             "phone_code": "222222"}).status_code == 409
    assert deleted == [["v-1"]]


# --- two people, one e-mail address -------------------------------------------
def test_a_second_signup_does_not_break_the_first(client, monkeypatch):
    """Whoever started first keeps a working code. Several attempts may be live at
    once; verification is by row id, so the code entered decides which one wins."""
    statements = []
    monkeypatch.setattr(auth, "execute", lambda sql, params=None: statements.append(
        (" ".join(sql.split()), list(params or []))))
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None:
                        None if "from users" in sql else {"id": "v-2"})
    monkeypatch.setattr(auth, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(auth, "send_sms", lambda *a, **k: True)
    res = client.post("/api/auth/register", json={
        "email": "shared@example.com", "password": "Abcdef12", "phone": "0501234567"})
    assert res.status_code == 200
    deletes = [(sql, p) for sql, p in statements if sql.startswith("delete")]
    assert len(deletes) == 1
    sql, params = deletes[0]
    assert "expires_at < now()" in sql, "a live attempt must survive a second signup"
    assert params == ["shared@example.com"], "and only this address is touched"


def test_expired_attempts_for_that_address_are_cleared(client, monkeypatch):
    """The flow tidies after itself, so the table can't grow forever."""
    statements = []
    monkeypatch.setattr(auth, "execute", lambda sql, params=None: statements.append(" ".join(sql.split())))
    monkeypatch.setattr(auth, "fetch_one", lambda sql, params=None:
                        None if "from users" in sql else {"id": "v-2"})
    monkeypatch.setattr(auth, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(auth, "send_sms", lambda *a, **k: True)
    client.post("/api/auth/register", json={
        "email": "shared@example.com", "password": "Abcdef12", "phone": "0501234567"})
    assert any("delete from signup_verifications where lower(email) = %s and expires_at < now()" in s
               for s in statements)
