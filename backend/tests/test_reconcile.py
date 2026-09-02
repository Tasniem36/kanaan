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


def _order(**over):
    o = {"id": ORDER_ID, "ziina_payment_id": "pi_1", "status": "pending",
         "payment_status": "pending", "total": 100, "stale": False}
    o.update(over)
    return o


@pytest.fixture
def acted(monkeypatch):
    """Capture the decisions instead of writing them."""
    calls = {"paid": [], "cancelled": []}
    monkeypatch.setattr(rec, "mark_paid", lambda order, request=None: calls["paid"].append(str(order["id"])))
    monkeypatch.setattr(rec, "cancel_and_restore", lambda oid: calls["cancelled"].append(oid))
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
    assert counts == {"paid": 0, "cancelled": 0, "waiting": 0, "unreachable": 1}
    assert acted["cancelled"] == []  # even though it is stale: we still have no answer


def test_a_young_undecided_payment_is_left_to_finish(monkeypatch, acted):
    _rows(monkeypatch, _order(stale=False))
    _intent(monkeypatch, "pending")
    assert rec.reconcile(apply=True)["waiting"] == 1
    assert acted == {"paid": [], "cancelled": []}


# --- releasing stock ---------------------------------------------------------
@pytest.mark.parametrize("status", sorted(rec.FAILED_STATUSES))
def test_releases_stock_on_a_definite_failure(monkeypatch, acted, status):
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


# --- the safety rails --------------------------------------------------------
def test_reports_without_applying_by_default(monkeypatch, acted):
    _rows(monkeypatch, _order(), _order(stale=True))
    _intent(monkeypatch, "completed")
    counts = rec.reconcile()
    assert counts["paid"] == 2                      # says what it found
    assert acted == {"paid": [], "cancelled": []}   # and touches nothing


def test_a_mistyped_stale_window_cannot_go_below_the_floor(monkeypatch):
    monkeypatch.setenv("PAYMENT_STALE_MINUTES", "1")
    assert rec._stale_minutes() == rec.MIN_STALE_MINUTES
    monkeypatch.setenv("PAYMENT_STALE_MINUTES", "not-a-number")
    assert rec._stale_minutes() == rec.STALE_MINUTES
