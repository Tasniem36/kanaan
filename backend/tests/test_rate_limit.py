"""The login/register brute-force limiter returns 429 once the per-IP window is
exhausted, without ever reaching the (patched-out) database once blocked."""
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
