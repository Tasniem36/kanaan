"""Unit tests for the auth primitives — no app, no DB."""
import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import security


def _request(token=None):
    headers = [(b"authorization", b"Bearer " + token.encode())] if token else []
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                    "headers": headers, "client": ("test", 1)})


def test_password_hash_roundtrip():
    h = security.hash_password("Sup3rSecret")
    assert h != "Sup3rSecret"
    assert security.verify_password("Sup3rSecret", h)
    assert not security.verify_password("wrong", h)


def test_valid_token_is_accepted():
    tok = security.sign_token({"id": "42", "role": "manager"})
    u = security.current_user(_request(tok))
    assert u == {"id": "42", "role": "manager"}


def test_token_signed_with_wrong_secret_is_rejected():
    forged = jwt.encode({"sub": "1", "role": "manager"}, "attacker-key", algorithm="HS256")
    with pytest.raises(HTTPException) as e:
        security.current_user(_request(forged))
    assert e.value.status_code == 401


def test_tampered_token_is_rejected():
    tok = security.sign_token({"id": "1", "role": "shopper"})
    with pytest.raises(HTTPException):
        security.current_user(_request(tok[:-3] + "aaa"))


def test_missing_token_is_401():
    with pytest.raises(HTTPException) as e:
        security.current_user(_request(None))
    assert e.value.status_code == 401


# --- retiring the sessions on other devices -----------------------------------
def test_a_token_from_a_closed_generation_is_refused(monkeypatch):
    """Changing a password raises the account's token_version; every token stamped
    with the old number stops working, which is what signs the other devices out."""
    monkeypatch.setattr(security, "fetch_one", lambda sql, params=None: {"token_version": 3})

    stale = security.sign_token({"id": "1", "role": "customer", "token_version": 2})
    with pytest.raises(HTTPException) as e:
        security.current_user(_request(stale))
    assert e.value.status_code == 401

    fresh = security.sign_token({"id": "1", "role": "customer", "token_version": 3})
    assert security.current_user(_request(fresh))["id"] == "1", "the current one still works"


def test_the_guest_facing_dependency_refuses_it_too(monkeypatch):
    """Checkout and order tracking resolve the caller through optional_user. A retired
    token must not still be able to order as that customer."""
    monkeypatch.setattr(security, "fetch_one", lambda sql, params=None: {"token_version": 5})
    stale = security.sign_token({"id": "1", "role": "customer", "token_version": 4})
    assert security.optional_user(_request(stale)) is None


def test_a_token_predating_the_column_still_works(monkeypatch):
    """The deploy that introduces this must not sign the whole shop out."""
    monkeypatch.setattr(security, "fetch_one", lambda sql, params=None: {"token_version": 0})
    legacy = jwt.encode({"sub": "1", "role": "customer"}, security.SECRET, algorithm="HS256")
    assert security.current_user(_request(legacy))["id"] == "1"


def test_a_deleted_account_cannot_go_on_using_its_token(monkeypatch):
    monkeypatch.setattr(security, "fetch_one", lambda sql, params=None: None)
    tok = security.sign_token({"id": "1", "role": "customer", "token_version": 0})
    with pytest.raises(HTTPException):
        security.current_user(_request(tok))


def test_require_manager_allows_manager():
    tok = security.sign_token({"id": "1", "role": "manager"})
    assert security.require_manager(_request(tok))["role"] == "manager"


def test_require_manager_forbids_shopper():
    tok = security.sign_token({"id": "1", "role": "shopper"})
    with pytest.raises(HTTPException) as e:
        security.require_manager(_request(tok))
    assert e.value.status_code == 403
