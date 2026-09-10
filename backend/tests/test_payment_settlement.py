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
from contextlib import contextmanager

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
    calls = {"cancelled": [], "paid": [], "why": []}
    monkeypatch.setattr(orders_mod, "cancel_and_restore",
                        lambda oid, *, why=None, request=None: calls["why"].append(why) or
                        calls["cancelled"].append(oid))
    monkeypatch.setattr(orders_mod, "mark_paid",
                        lambda order, request=None, **k: calls["paid"].append(str(order["id"])))
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
# mark_paid does its work inside one transaction on the pool, so these script that
# transaction rather than patching a helper per statement. Answers are matched on a
# fragment of the SQL, so a test says what a statement should come back with without
# having to count the statements around it.
class _Cursor:
    def __init__(self, answers):
        self.answers, self.sql, self._last = answers, [], None

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sql.append(flat)
        self._last = next((v for k, v in self.answers.items() if k in flat), None)

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._last or []

    def ran(self, fragment):
        """Whether any statement in the transaction contained this."""
        return any(fragment in s for s in self.sql)


class _Txn:
    """Stands in for the pool, the connection and the transaction at once — they are
    only ever used together, as one `with`."""

    def __init__(self, answers):
        self.cur = _Cursor(answers)

    def connection(self):
        return _open(self)

    def transaction(self):
        return _open(None)

    def cursor(self):
        return _open(self.cur)


@contextmanager
def _open(v):
    yield v


@pytest.fixture
def settling(monkeypatch):
    """Script mark_paid's transaction and hand back its cursor to assert against."""
    def install(**answers):
        txn = _Txn(answers)
        monkeypatch.setattr(orders_mod, "pool", txn)
        return txn.cur
    return install


def _claimed(status="pending"):
    """A locked row saying `status`, and a claim that wins."""
    return {"for update": {"status": status},
            "is distinct from 'paid'": _order(payment_status="paid", status="paid")}


TAKE_OFF_SHELF = "stock = p.stock - s.qty"


@pytest.fixture
def quiet(monkeypatch):
    """mark_paid's alarms, silenced. They are their own tests."""
    for name in ("notify_new_order", "_notify_new_order_admins", "_send_order_whatsapp", "log_action"):
        monkeypatch.setattr(orders_mod, name, lambda *a, **k: None)


# --- an order cancelled before the money landed comes back with its stock ----
def test_confirming_a_cancelled_order_takes_its_stock_back_off_the_shelf(
        client, owner, monkeypatch, quiet, settling):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order(status="cancelled"))
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent("completed"))
    cur = settling(**_claimed("cancelled"))
    r = client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert r.json() == {"paid": True, "status": "paid"}
    # cancel_and_restore had put these units back; the payment makes the order real
    # again, so they leave the shelf a second time or the shop oversells them
    assert cur.ran(TAKE_OFF_SHELF)


def test_confirming_a_live_order_does_not_double_deduct(client, owner, monkeypatch, quiet, settling):
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: _order())
    monkeypatch.setattr(orders_mod, "get_payment_intent", _intent("completed"))
    cur = settling(**_claimed("pending"))
    client.post(f"/api/orders/{ORDER_ID}/confirm-payment")
    assert not cur.ran(TAKE_OFF_SHELF)  # taken at checkout and never given back


# --- one settle per order, whoever gets there first --------------------------
@pytest.fixture
def raised(monkeypatch):
    """Everything mark_paid sets off once an order becomes real."""
    calls = []
    monkeypatch.setattr(orders_mod, "notify_new_order", lambda order: calls.append("manager"))
    monkeypatch.setattr(orders_mod, "_notify_new_order_admins", lambda order: calls.append("bell"))
    monkeypatch.setattr(orders_mod, "_send_order_whatsapp", lambda order, request=None: calls.append("whatsapp"))
    monkeypatch.setattr(orders_mod, "log_action", lambda **k: None)
    return calls


def test_settling_an_order_that_was_already_paid_raises_nothing_twice(raised, settling):
    """The return page's polling and the reconcile sweep can reach mark_paid for the
    same order at the same moment, each having read payment_status in an earlier,
    separate query. The write is what decides: no row means someone else settled it,
    and the loser must not send a second billed WhatsApp template, ring the managers
    again, or take the stock off the shelf twice.
    """
    cur = settling(**{"for update": {"status": "cancelled"}})  # the claim wins nothing
    assert orders_mod.mark_paid(_order(status="cancelled")) is None
    assert raised == []
    assert not cur.ran(TAKE_OFF_SHELF)


def test_settling_an_order_that_has_been_deleted_does_nothing(raised, settling):
    cur = settling()  # not even a row to lock
    assert orders_mod.mark_paid(_order()) is None
    assert raised == []
    assert not cur.ran("update orders")


def test_settling_claims_the_order_in_the_write_itself(raised, settling):
    cur = settling(**_claimed())
    assert orders_mod.mark_paid(_order())["payment_status"] == "paid"
    assert cur.ran("payment_status is distinct from 'paid'"), (
        "the check has to be part of the update, or two settles both pass it"
    )
    assert raised == ["manager", "bell", "whatsapp"]


def test_the_whole_settle_happens_in_one_transaction(raised, settling):
    """Nothing comes back for a half-settled order: unresolved_orders in reconcile.py
    stops looking at one the moment it is paid. So the flip, the stock and the
    timeline point have to be all-or-nothing."""
    cur = settling(**_claimed("cancelled"))
    orders_mod.mark_paid(_order(status="cancelled"))
    assert [s.split(" ", 2)[0] for s in cur.sql] == ["select", "update", "update", "insert", "select"]


# --- the stock follows the locked row, not the caller's copy ------------------
def test_a_stale_pending_copy_still_takes_the_stock_off_the_shelf(raised, settling):
    """The caller read this order before a Ziina call that can take twenty seconds —
    and in the sweep, before every other order's. A manager who cancelled inside that
    window has already put the stock back. Deciding from the caller's copy leaves it
    sitting on the shelf with the order paid, and the shop sells the same jar twice."""
    cur = settling(**_claimed("cancelled"))
    orders_mod.mark_paid(_order(status="pending"))
    assert cur.ran(TAKE_OFF_SHELF)


def test_a_stale_cancelled_copy_does_not_deduct_a_revived_order_twice(raised, settling):
    """The mirror image: the caller read 'cancelled', and a manager has since revived
    the order, which took its stock off again. Deducting on the stale copy takes it
    twice and the shelf ends up owing units nobody ordered."""
    cur = settling(**_claimed("preparing"))
    orders_mod.mark_paid(_order(status="cancelled"))
    assert not cur.ran(TAKE_OFF_SHELF)


# --- the alarms are raised independently -------------------------------------
def test_one_alarm_failing_does_not_silence_the_ones_after_it(monkeypatch, settling):
    """These run after the settle has committed, and nothing revisits a paid order, so
    a message lost here is lost for good. Losing the manager's alert to a Telegram
    outage must not also cost the customer their confirmation."""
    calls = []
    monkeypatch.setattr(orders_mod, "notify_new_order",
                        lambda order: (_ for _ in ()).throw(RuntimeError("telegram is down")))
    monkeypatch.setattr(orders_mod, "_notify_new_order_admins", lambda order: calls.append("bell"))
    monkeypatch.setattr(orders_mod, "_send_order_whatsapp", lambda order, request=None: calls.append("whatsapp"))
    monkeypatch.setattr(orders_mod, "log_action", lambda **k: calls.append("audit"))
    settling(**_claimed())
    assert orders_mod.mark_paid(_order())["payment_status"] == "paid", "still paid, whatever was said"
    assert calls == ["bell", "whatsapp", "audit"]


# --- the shop's record of its own money --------------------------------------
def _rows_logged(monkeypatch):
    rows = []
    monkeypatch.setattr(orders_mod, "log_action", lambda **k: rows.append(k))
    return rows


def test_a_settled_payment_is_recorded_with_who_noticed_it(monkeypatch, quiet, settling):
    """Recorded inside mark_paid, so a payment the sweep found leaves the same row as
    one the browser reported. The sweep has no other witness: before this, the only
    trace of a cron settle was a line of stdout in a cron log."""
    rows = _rows_logged(monkeypatch)
    settling(**_claimed())
    orders_mod.mark_paid(_order(), by="sweep")
    assert rows[0]["action"] == "payment_confirmed"
    assert rows[0]["user_id"] == "owner"
    assert rows[0]["detail"] == {"order_id": ORDER_ID, "total": 100, "by": "sweep"}


def test_a_settle_that_did_nothing_records_nothing(monkeypatch, quiet, settling):
    """Two settles racing must not read afterwards as two payments."""
    rows = _rows_logged(monkeypatch)
    settling(**{"for update": {"status": "pending"}})  # the claim wins nothing
    assert orders_mod.mark_paid(_order()) is None
    assert rows == []


def test_a_released_order_is_recorded_with_the_reason_it_was_released(monkeypatch, settling):
    rows = _rows_logged(monkeypatch)
    settling(**{"is distinct from 'cancelled'": {"user_id": "owner", "total": 90}})
    assert orders_mod.cancel_and_restore(ORDER_ID, why="expired") is True
    assert rows[0]["action"] == "payment_released"
    assert rows[0]["detail"] == {"order_id": ORDER_ID, "total": 90, "why": "expired"}


def test_releasing_an_order_that_was_already_cancelled_records_nothing(monkeypatch, settling):
    """A reloaded return page, or one racing the sweep. One release, one row."""
    rows = _rows_logged(monkeypatch)
    settling()  # nothing left to cancel
    assert orders_mod.cancel_and_restore(ORDER_ID, why="expired") is False
    assert rows == []


def test_a_failing_audit_row_cannot_fail_a_payment_that_went_through(monkeypatch, quiet, settling):
    """The money is committed before the row is written. A shopper must never be shown
    an error for a payment that succeeded, because a log insert didn't."""
    monkeypatch.setattr(orders_mod, "log_action",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("audit is down")))
    settling(**_claimed())
    assert orders_mod.mark_paid(_order())["payment_status"] == "paid"


# --- the guest's e-mail follows the money, not the button --------------------
def test_the_guest_who_cannot_sign_in_is_the_one_e_mailed(monkeypatch):
    monkeypatch.setattr(orders_mod, "_can_sign_in", lambda uid: False)
    monkeypatch.setattr(orders_mod, "fetch_one", lambda sql, params=None: {"email": "guest@example.com"})
    assert orders_mod._guest_email_for(_order()) == "guest@example.com"


def test_a_customer_with_a_real_account_is_not(monkeypatch):
    """They read the order in حسابي. This mail was only ever the guest's substitute
    for having somewhere to read it."""
    monkeypatch.setattr(orders_mod, "_can_sign_in", lambda uid: True)
    monkeypatch.setattr(orders_mod, "fetch_one",
                        lambda sql, params=None: pytest.fail("no address needs looking up"))
    assert orders_mod._guest_email_for(_order()) is None


def test_an_order_with_no_account_behind_it_is_not():
    """A guest who left no e-mail has no shadow account, and nothing to write to."""
    assert orders_mod._guest_email_for(_order(user_id=None)) is None


def test_settling_is_what_sends_the_guest_their_confirmation(monkeypatch, quiet, settling):
    """Not the hand-off to Ziina. Nothing is paid at that point, and an abandoned
    checkout is released within the half hour — leaving the customer holding an
    e-mail that says their order was paid for."""
    sent = []
    monkeypatch.setattr(orders_mod, "_guest_email_for", lambda order: "guest@example.com")
    monkeypatch.setattr(orders_mod, "_send_order_email",
                        lambda order, email, request: sent.append(email))
    settling(**_claimed())
    orders_mod.mark_paid(_order())
    assert sent == ["guest@example.com"]


def test_a_settle_that_did_nothing_sends_no_e_mail(monkeypatch, quiet, settling):
    """Two settles racing must not mean two confirmations."""
    sent = []
    monkeypatch.setattr(orders_mod, "_guest_email_for", lambda order: "guest@example.com")
    monkeypatch.setattr(orders_mod, "_send_order_email",
                        lambda order, email, request: sent.append(email))
    settling(**{"for update": {"status": "pending"}})   # the claim wins nothing
    assert orders_mod.mark_paid(_order()) is None
    assert sent == []


@pytest.mark.parametrize("order,expected", [
    ({"payment_method": "cod", "payment_status": "unpaid"}, "الدفع عند الاستلام"),
    ({"payment_method": "ziina", "payment_status": "paid"}, "مدفوع إلكترونياً"),
    ({"payment_method": "ziina", "payment_status": "unpaid"}, "بانتظار الدفع"),
])
def test_the_e_mail_never_claims_money_that_has_not_arrived(order, expected):
    """Read off payment_method alone, it told a guest their order was paid while they
    were still looking at the payment page."""
    body = orders_mod._order_email_body(
        {"id": ORDER_ID, "customer_name": "تسنيم", "total": 90, **order}, "https://x/track/1")
    assert expected in body
