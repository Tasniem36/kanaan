"""The time an order is stamped with, in the shop's own clock.

Postgres hands these back in UTC, and the container had no timezone database, so
every alert read four hours behind the shop. Nobody noticed because a developer's
machine has tzdata and the fallback was silent.
"""
import datetime
import importlib
import sys

import pytest

import notify

UTC_NOON = datetime.datetime(2026, 9, 10, 12, 0, tzinfo=datetime.timezone.utc)


def test_an_order_is_stamped_in_the_shops_own_time():
    """12:00 UTC is 16:00 in Dubai, and 16:00 is what the shop is told."""
    assert notify._order_time({"created_at": UTC_NOON}) == "2026-09-10 16:00"


def test_the_time_is_right_even_with_no_timezone_database(monkeypatch):
    """python:*-slim ships without one. The UAE has never observed DST, so a fixed
    +04:00 is not an approximation — it is the same answer, always."""
    real = sys.modules.get("zoneinfo")
    monkeypatch.setitem(sys.modules, "zoneinfo", None)   # import raises, as in the container
    try:
        reloaded = importlib.reload(notify)
        assert reloaded._order_time({"created_at": UTC_NOON}) == "2026-09-10 16:00", (
            "without tzdata this fell back to UTC and read 12:00"
        )
    finally:
        monkeypatch.setitem(sys.modules, "zoneinfo", real)
        importlib.reload(notify)


def test_a_naive_timestamp_is_not_mangled():
    """Nothing in the app stores one, but _order_time must not turn a missing or odd
    value into a traceback on the alert that tells the shop it has an order."""
    assert notify._order_time({}) == ""
    assert notify._order_time({"created_at": "already a string"}) == "already a string"


@pytest.mark.parametrize("utc,shop", [
    ("2026-01-01T20:30:00+00:00", "2026-01-02 00:30"),   # crosses midnight into the next day
    ("2026-06-15T23:00:00+00:00", "2026-06-16 03:00"),   # and again in summer: no DST here
])
def test_the_shop_day_rolls_over_at_the_shops_midnight(utc, shop):
    assert notify._order_time({"created_at": datetime.datetime.fromisoformat(utc)}) == shop
