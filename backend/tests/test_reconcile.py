"""The sweep that finishes payments the return page never got to report.

cancel_payment is deliberately unwilling to cancel an order on an unresolved
payment (see test_payment_settlement.py). That only works because this job exists to
resolve them later — so these tests care most about two things: that it settles a
payment nobody told us about, and that it never decides anything on silence.
"""
import pytest
from fastapi import HTTPException

import reconcile as rec

ORDER_ID = "0f1d4e0e-2222-4000-8000-000000000000"
OTHER_ID = "0f1d4e0e-2222-4000-8000-000000000001"


def _raise(e):
    raise e


def _order(**over):
    o = {"id": ORDER_ID, "ziina_payment_id": "pi_1", "status": "pending",
         "payment_status": "pending", "total": 100, "stale": False}
    o.update(over)
    return o


@pytest.fixture
def acted(monkeypatch):
    """Capture the decisions instead of writing them.

    Both stand-ins answer the way the real ones do — "this call was the one that did
    it" — because the sweep now counts on that answer to tell work it did from work
    the return page had already done.
    """
    calls = {"paid": [], "cancelled": [], "why": []}

    def _paid(order, request=None, *, by="return"):
        calls["paid"].append(str(order["id"]))
        return {**order, "payment_status": "paid"}

    def _cancelled(oid, *, why=None, request=None):
        calls["cancelled"].append(oid)
        calls["why"].append(why)
        return True

    monkeypatch.setattr(rec, "mark_paid", _paid)
    monkeypatch.setattr(rec, "cancel_and_restore", _cancelled)
    return calls


def _rows(monkeypatch, *orders):
    monkeypatch.setattr(rec, "fetch_all", lambda sql, params=None: list(orders))


def _intent(monkeypatch, status):
    monkeypatch.setattr(rec, "get_payment_intent", lambda pid: {"status": status})


# --- the case the job exists for --------------------------------------------
def test_settles_a_payment_the_browser_never_reported(monkeypatch, acted):
    _rows(monkeypatch, _order())
    _intent(monkeypatch, "completed")
    assert rec.reconcile(apply=True)["paid"] == 1
    assert acted["paid"] == [ORDER_ID]


def test_recovers_an_order_cancelled_while_its_payment_was_in_flight(monkeypatch, acted):
    _rows(monkeypatch, _order(status="cancelled"))
    _intent(monkeypatch, "completed")
    rec.reconcile(apply=True)
    assert acted["paid"] == [ORDER_ID]  # mark_paid takes its stock back off the shelf
    assert acted["cancelled"] == []


# --- nothing is decided on silence ------------------------------------------
def test_an_unreachable_ziina_changes_nothing(monkeypatch, acted):
    _rows(monkeypatch, _order(stale=True))
    monkeypatch.setattr(rec, "get_payment_intent",
                        lambda pid: (_ for _ in ()).throw(HTTPException(502, "Could not verify the payment")))
    counts = rec.reconcile(apply=True)
    assert counts == {"paid": 0, "cancelled": 0, "waiting": 0, "unreachable": 1,
                      "already": 0, "failed": 0}
    assert acted["cancelled"] == []  # even though it is stale: we still have no answer


def test_a_young_undecided_payment_is_left_to_finish(monkeypatch, acted):
    _rows(monkeypatch, _order(stale=False))
    _intent(monkeypatch, "pending")
    assert rec.reconcile(apply=True)["waiting"] == 1
    assert not acted["paid"] and not acted["cancelled"]


# --- releasing stock ---------------------------------------------------------
@pytest.mark.parametrize("status", sorted(rec.REFUSED_STATUSES))
def test_releases_stock_on_a_definite_refusal(monkeypatch, acted, status):
    _rows(monkeypatch, _order(stale=False))
    _intent(monkeypatch, status)
    assert rec.reconcile(apply=True)["cancelled"] == 1
    assert acted["cancelled"] == [ORDER_ID]


def test_releases_stock_once_an_undecided_payment_has_gone_stale(monkeypatch, acted):
    _rows(monkeypatch, _order(stale=True))
    _intent(monkeypatch, "pending")
    assert rec.reconcile(apply=True)["cancelled"] == 1
    assert acted["cancelled"] == [ORDER_ID]


def test_does_not_cancel_an_order_that_is_already_cancelled(monkeypatch, acted):
    _rows(monkeypatch, _order(status="cancelled", stale=True))
    _intent(monkeypatch, "failed")
    rec.reconcile(apply=True)
    assert acted["cancelled"] == []


# --- one bad order must not end the run --------------------------------------
def test_an_answer_that_is_not_even_json_only_costs_that_one_order(monkeypatch, acted):
    """ziina.get_payment_intent parses the body outside its own try, so a gateway
    answering with an HTML error page raises ValueError, not HTTPException. Guarding
    only HTTPException here left every later order unchecked: the paid ones unsettled
    and the stale ones still holding stock."""
    _rows(monkeypatch, _order(), _order(id=OTHER_ID, ziina_payment_id="pi_2"))
    monkeypatch.setattr(rec, "get_payment_intent", lambda pid: (
        {"status": "completed"} if pid == "pi_2" else _raise(ValueError("Expecting value"))))
    counts = rec.reconcile(apply=True)
    assert acted["paid"] == [OTHER_ID]  # the sweep carried on past the bad answer
    assert (counts["unreachable"], counts["paid"]) == (1, 1)


def test_an_order_that_cannot_be_settled_is_counted_rather_than_fatal(monkeypatch, acted):
    """A dropped connection or a deadlock settling one order. It stays unresolved for
    the next run — but the run has to finish, and say that one didn't."""
    _rows(monkeypatch, _order(), _order(id=OTHER_ID, ziina_payment_id="pi_2"))
    _intent(monkeypatch, "completed")
    settled = rec.mark_paid
    monkeypatch.setattr(rec, "mark_paid", lambda order, request=None, **k: (
        _raise(RuntimeError("the connection is closed")) if str(order["id"]) == ORDER_ID
        else settled(order)))
    counts = rec.reconcile(apply=True)
    assert acted["paid"] == [OTHER_ID]
    assert (counts["paid"], counts["failed"]) == (1, 1)  # not counted as settled


# --- the safety rails --------------------------------------------------------
def test_reports_without_applying_by_default(monkeypatch, acted):
    _rows(monkeypatch, _order(), _order(stale=True))
    _intent(monkeypatch, "completed")
    counts = rec.reconcile()
    assert counts["paid"] == 2                      # says what it found
    assert not acted["paid"] and not acted["cancelled"]  # and touches nothing


def test_a_mistyped_stale_window_cannot_go_below_the_floor(monkeypatch):
    monkeypatch.setenv("PAYMENT_STALE_MINUTES", "1")
    assert rec._stale_minutes() == rec.MIN_STALE_MINUTES
    monkeypatch.setenv("PAYMENT_STALE_MINUTES", "not-a-number")
    assert rec._stale_minutes() == rec.STALE_MINUTES


# --- the log says what the run actually did -----------------------------------
def test_a_payment_the_return_page_already_settled_is_not_counted_as_work(monkeypatch, acted):
    """This run read the order, and the customer's browser came back and settled it in
    the seconds before the run got there. mark_paid says so by returning nothing. A
    log claiming nine settled payments should mean nine customers who would otherwise
    still be waiting on one."""
    _rows(monkeypatch, _order())
    _intent(monkeypatch, "completed")
    monkeypatch.setattr(rec, "mark_paid", lambda order, request=None, **k: None)
    counts = rec.reconcile(apply=True)
    assert (counts["paid"], counts["already"], counts["failed"]) == (0, 1, 0)


def test_an_order_released_by_someone_else_is_not_counted_as_work_either(monkeypatch, acted):
    _rows(monkeypatch, _order(stale=True))
    _intent(monkeypatch, "pending")
    monkeypatch.setattr(rec, "cancel_and_restore", lambda oid, **k: False)
    counts = rec.reconcile(apply=True)
    assert (counts["cancelled"], counts["already"]) == (0, 1)


# --- what the sweep puts in the shop's record ---------------------------------
def test_the_sweep_says_it_was_the_one_that_noticed(monkeypatch, acted):
    """Whether the return page is doing its job or cron is quietly doing it for them
    is only visible if the row says which."""
    seen = {}
    _rows(monkeypatch, _order())
    _intent(monkeypatch, "completed")
    monkeypatch.setattr(rec, "mark_paid",
                        lambda order, request=None, *, by=None: seen.setdefault("by", by))
    rec.reconcile(apply=True)
    assert seen["by"] == "sweep"


def test_an_order_released_for_going_stale_records_that_as_the_reason(monkeypatch, acted):
    _rows(monkeypatch, _order(stale=True))
    _intent(monkeypatch, "pending")
    rec.reconcile(apply=True)
    assert acted["why"] == [f"unresolved for over {rec._stale_minutes()}m"]


def test_a_definite_refusal_is_released_with_ziina_s_own_word_for_it(monkeypatch, acted):
    """"failed", not "unresolved for over 1440m": the log should say what the shop
    was told, so a run of declines reads differently from a run of people wandering
    off. ("expired" no longer belongs here — see below, it is not a refusal.)"""
    _rows(monkeypatch, _order())
    _intent(monkeypatch, "failed")
    rec.reconcile(apply=True)
    assert acted["why"] == ["failed"]


# --- a timed-out attempt is not a refusal ------------------------------------
def test_an_expired_intent_waits_out_the_window_like_any_other(monkeypatch, acted):
    """Expired used to sit with failed and cancelled, so an order died the moment
    Ziina timed its intent out — however long the shop had said to wait, which made
    PAYMENT_STALE_MINUTES close to decorative for anyone who took their time.

    It is not a refusal. Nobody declined anything; one attempt ran out of clock, and
    the tracking page hands out a fresh payment page for exactly this. So it waits.
    """
    _rows(monkeypatch, _order(stale=False))
    _intent(monkeypatch, "expired")
    assert rec.reconcile(apply=True)["waiting"] == 1
    assert acted["cancelled"] == [], "the customer can still come back and pay"


def test_an_expired_intent_is_released_once_the_window_is_up(monkeypatch, acted):
    """It waits, it does not linger for ever: the shelf is still owed its stock."""
    _rows(monkeypatch, _order(stale=True))
    _intent(monkeypatch, "expired")
    assert rec.reconcile(apply=True)["cancelled"] == 1
    assert acted["cancelled"] == [ORDER_ID]
