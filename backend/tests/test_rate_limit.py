"""The login/register brute-force limiter returns 429 once the per-IP window is
exhausted, without ever reaching the (patched-out) database once blocked."""
import pytest
from fastapi import HTTPException

import routers.auth as auth_mod


def test_login_is_rate_limited(client, monkeypatch):
    # every attempt is a valid-shaped but wrong login -> 401, until the limiter trips
    monkeypatch.setattr(auth_mod, "fetch_one", lambda sql, params=None: None)
    body = {"email": "a@b.com", "password": "whatever"}

    codes = [client.post("/api/auth/login", json=body).status_code for _ in range(11)]

    assert codes[:10] == [401] * 10   # limit is 10/min
    assert codes[10] == 429


def test_register_is_rate_limited(client, monkeypatch):
    # short-circuit before any DB work; we only care that the 6th call is throttled
    monkeypatch.setattr(auth_mod, "fetch_one", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not reach DB")))
    body = {}  # missing fields -> 400 before DB, but after the limiter

    codes = [client.post("/api/auth/register", json=body).status_code for _ in range(6)]

    assert codes[:5] == [400] * 5     # limit is 5/min
    assert codes[5] == 429


def test_a_shared_address_does_not_pool_one_budget(monkeypatch):
    """A family at home shares an IP. Keyed by IP, one person writing reviews would
    throttle the rest of the household; keyed by customer, they're independent."""
    import ratelimit
    ratelimit._hits.clear()

    class Req:  # same address for both callers
        headers = {}
        client = type("C", (), {"host": "5.5.5.5"})()

    req = Req()
    for _ in range(20):
        ratelimit.rate_limit(req, bucket="review", limit=20, window=60, key="customer-a")
    # customer A is now at the limit
    with pytest.raises(HTTPException) as exc:
        ratelimit.rate_limit(req, bucket="review", limit=20, window=60, key="customer-a")
    assert exc.value.status_code == 429
    # customer B, same wifi, is unaffected
    ratelimit.rate_limit(req, bucket="review", limit=20, window=60, key="customer-b")


def test_sign_in_stays_keyed_to_the_address(monkeypatch):
    """No trusted identity exists yet there, and the address is what needs limiting."""
    import ratelimit
    ratelimit._hits.clear()

    class Req:
        headers = {}
        client = type("C", (), {"host": "6.6.6.6"})()

    for _ in range(10):
        ratelimit.rate_limit(Req(), bucket="login", limit=10, window=60)
    with pytest.raises(HTTPException):
        ratelimit.rate_limit(Req(), bucket="login", limit=10, window=60)
