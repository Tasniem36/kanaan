"""Shared test setup.

Two things have to happen BEFORE the app is imported:
  1. JWT_SECRET must exist, or security.py refuses to start (that guard is itself
     under test in test_jwt_secret_guard.py, via a subprocess).
  2. db.py opens a real connection pool at import time. We never touch a real DB
     in these tests — every handler's db call is monkeypatched — but we stub the
     pool so import doesn't spend time trying to reach Postgres.
"""
import os

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-chars-long")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.pop("CORS_ORIGIN", None)  # exercise the "no origins" default
os.environ.pop("ENV", None)

# Stub the connection pool before anything imports db.py, so no socket is opened.
import psycopg_pool

# Kept so the opt-in integration tests (test_db_integration.py) can build a real
# pool against a scratch database. Nothing else should use it.
REAL_CONNECTION_POOL = psycopg_pool.ConnectionPool


class _FakePool:
    def __init__(self, *a, **k):
        pass

    def connection(self):  # pragma: no cover - only hit if a test forgets to patch
        raise RuntimeError("real DB access in a test — patch fetch_one/execute instead")


psycopg_pool.ConnectionPool = _FakePool

import pytest
from fastapi.testclient import TestClient

import main
from security import current_user, optional_user, sign_token


@pytest.fixture
def app():
    return main.app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def as_user(app):
    """Impersonate a user dict. Overrides both auth dependencies: endpoints open to
    guests (checkout, order tracking, the payment callbacks) resolve the caller
    through optional_user, so overriding current_user alone would leave them
    looking like an anonymous visitor."""
    def _set(user):
        app.dependency_overrides[current_user] = lambda: user
        app.dependency_overrides[optional_user] = lambda: user
    yield _set
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    import ratelimit
    ratelimit._hits.clear()
    yield
    ratelimit._hits.clear()


def token_for(uid="u-1", role="shopper"):
    return sign_token({"id": uid, "role": role})
