"""What the Ziina client is allowed to conclude from a reply.

An answer we cannot read is not an answer. Returning an empty dict for one let a 200
from a proxy or a gateway read as "the payment API replied fine and had nothing to
say", which is the most dangerous reading available:

  · create_payment_intent handed back no redirect_url, and the checkout — which
    treats a missing one as "this order is cash on delivery" — emptied the basket and
    confirmed an order nobody had paid for;
  · get_payment_intent handed back an intent with no status, which the reconcile
    sweep reads as unresolved, and half an hour later releases the order on the
    strength of an answer we never got.

Both are now the same 502 as not being able to ask at all, which every caller already
knows how to leave alone.
"""
import pytest
from fastapi import HTTPException

import ziina


_UNPARSEABLE = object()


class _Res:
    """A requests response, as much of one as this module touches. Left to itself it
    is a body that will not parse — the case all of this is about."""

    def __init__(self, *, ok=True, body=b"{}", json=_UNPARSEABLE):
        self.ok, self.content, self._json = ok, body, json

    def json(self):
        if self._json is _UNPARSEABLE:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._json


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setenv("ZIINA_API_KEY", "sk_test_not_a_real_key")


def _answers(monkeypatch, verb, res):
    monkeypatch.setattr(ziina.requests, verb, lambda *a, **k: res)


def _create():
    return ziina.create_payment_intent(amount_fils=9000, success_url="s://ok",
                                       cancel_url="s://no", message="طلب")


# --- an unreadable success is a 502, not an empty success ---------------------
@pytest.mark.parametrize("res", [
    _Res(body=b"<html>502 Bad Gateway</html>"),   # a gateway's error page behind a 200
    _Res(body=b""),                               # a 200 with nothing in it at all
    _Res(json=[]),                                # readable, but not an object
    _Res(json=None),                              # a literal JSON null
], ids=["html", "empty", "list", "null"])
@pytest.mark.parametrize("verb,call", [("post", _create), ("get", lambda: ziina.get_payment_intent("pi_1"))])
def test_a_200_we_cannot_read_is_refused(monkeypatch, verb, call, res):
    _answers(monkeypatch, verb, res)
    with pytest.raises(HTTPException) as e:
        call()
    assert e.value.status_code == 502


def test_an_unreadable_error_body_keeps_the_caller_s_own_message(monkeypatch):
    """An error response we can't parse was always fine to shrug at — the not-ok check
    has its own wording for it, and that must not be replaced by a vaguer one."""
    _answers(monkeypatch, "get", _Res(ok=False, body=b"<html>oops</html>"))
    with pytest.raises(HTTPException) as e:
        ziina.get_payment_intent("pi_1")
    assert e.value.detail == "Could not verify the payment"


def test_ziina_s_own_error_message_is_passed_through(monkeypatch):
    _answers(monkeypatch, "post", _Res(ok=False, json={"message": "Amount is too small"}))
    with pytest.raises(HTTPException) as e:
        _create()
    assert e.value.detail == "Amount is too small"


# --- a created intent has to be somewhere to send the shopper ----------------
def test_an_intent_without_a_payment_page_is_refused(monkeypatch):
    """Nowhere to send them is not a payment. Letting this through returned a null
    redirect_url, and routers/orders read that as a cash-on-delivery order: basket
    emptied, order confirmed on screen, nothing paid, and no ziina_payment_id for the
    sweep to ever find it by."""
    _answers(monkeypatch, "post", _Res(json={"id": "pi_1", "status": "pending"}))
    with pytest.raises(HTTPException) as e:
        _create()
    assert "payment page" in e.value.detail


def test_a_created_intent_comes_back_whole(monkeypatch):
    _answers(monkeypatch, "post", _Res(json={"id": "pi_1", "redirect_url": "https://pay.ziina/x"}))
    assert _create() == {"id": "pi_1", "redirect_url": "https://pay.ziina/x"}


# --- silence is not a status --------------------------------------------------
def test_an_intent_with_no_status_is_silence_not_an_unresolved_payment(monkeypatch):
    """Passed back as a status this code doesn't recognise, it would look exactly like
    a card still being authorised — and the staleness rule releases those."""
    _answers(monkeypatch, "get", _Res(json={"payment_intent": {"id": "pi_1"}}))
    with pytest.raises(HTTPException) as e:
        ziina.get_payment_intent("pi_1")
    assert e.value.status_code == 502


@pytest.mark.parametrize("body", [
    {"status": "completed"},
    {"payment_intent": {"status": "completed"}},
    {"result": {"status": "completed"}},
])
def test_the_status_is_found_wherever_ziina_puts_it(monkeypatch, body):
    _answers(monkeypatch, "get", _Res(json=body))
    assert ziina.get_payment_intent("pi_1")["status"] == "completed"
