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


def test_require_manager_allows_manager():
    tok = security.sign_token({"id": "1", "role": "manager"})
    assert security.require_manager(_request(tok))["role"] == "manager"


def test_require_manager_forbids_shopper():
    tok = security.sign_token({"id": "1", "role": "shopper"})
    with pytest.raises(HTTPException) as e:
        security.require_manager(_request(tok))
    assert e.value.status_code == 403
