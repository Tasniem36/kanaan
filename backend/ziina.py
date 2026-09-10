"""Minimal Ziina Payments client. Docs: https://docs.ziina.com/api-reference/payment-intent"""
import os

import requests
from fastapi import HTTPException

BASE = "https://api-v2.ziina.com/api"


def _headers():
    key = os.getenv("ZIINA_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Ziina is not configured on the server")
    return {"Authorization": f"Bearer {key}"}


def _body(res) -> dict:
    """Ziina's answer as a dict — or the 502 that an unreadable answer really is.

    A proxy or a gateway in front of the API answers with an HTML error page, not
    JSON, and parsing that raises a bare ValueError from inside a helper everyone
    calls — escaping callers that guard HTTPException, which is every one of them.
    That aborted the whole reconcile sweep on one bad response.

    Shrugging at an unreadable ERROR body is right: the not-ok check in each caller
    has its own message for that. Shrugging at an unreadable SUCCESS is not, because
    an empty dict then reads as a payment API that answered fine and had nothing to
    say — the most dangerous thing it could be taken to mean. It walked a shopper
    into the cash-on-delivery confirmation for a payment page that was never created,
    and told the sweep an intent had no status, which thirty minutes later releases an
    order that may well have been paid for. We asked and we did not hear: that is the
    same 502 as not being able to ask at all, and every caller already handles it.
    """
    try:
        data = res.json() if res.content else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        if res.ok:
            raise HTTPException(status_code=502, detail="Could not read Ziina's answer")
        return {}
    return data


def create_payment_intent(*, amount_fils, success_url, cancel_url, message):
    """amount_fils: integer in fils (100 AED = 10000). Returns dict with id, redirect_url, status."""
    try:
        res = requests.post(
            f"{BASE}/payment_intent",
            headers=_headers(),
            json={
                "amount": amount_fils,
                "currency_code": "AED",
                "message": message,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "failure_url": cancel_url,
                "test": os.getenv("ZIINA_TEST") == "true",
            },
            timeout=20,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Ziina: {e}")
    data = _body(res)
    if not res.ok:
        raise HTTPException(status_code=502, detail=data.get("message") or "Could not create the Ziina payment")
    if not data.get("redirect_url"):
        # A 200 with nowhere to send the shopper is not a payment. Saying so here is
        # what stops the checkout falling through to its cash-on-delivery branch,
        # which empties the basket and confirms an order nobody has paid for. The
        # caller cancels the order on this and the shopper sees the error, basket
        # intact, which is the truth.
        raise HTTPException(status_code=502, detail="Ziina did not return a payment page")
    if not data.get("id"):
        # A payment page we cannot name is worse than none at all. The id is the only
        # handle the shop keeps on this payment: reconcile.py looks for orders whose
        # ziina_payment_id is not null, so an order stored without one can never be
        # asked about again. The shopper would reach a real payment page, pay, and
        # sit outside every mechanism that settles or releases an order — holding its
        # stock for good. Refusing here cancels the order and gives them the error.
        raise HTTPException(status_code=502, detail="Ziina did not identify the payment")
    return data


def get_payment_intent(pid):
    try:
        res = requests.get(f"{BASE}/payment_intent/{pid}", headers=_headers(), timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Could not verify the payment: {e}")
    data = _body(res)
    if not res.ok:
        raise HTTPException(status_code=502, detail=data.get("message") or "Could not verify the payment")
    pi = data.get("payment_intent") or data.get("result") or data
    pi = pi if isinstance(pi, dict) else {}
    print("[ziina] intent", pid, "status =", pi.get("status"), "| keys:", ",".join(data.keys()))
    if not pi.get("status"):
        # An intent with no status at all is not an unresolved payment, it is silence
        # — and passing it back as one would let the staleness rule in reconcile.py
        # release the order half an hour later on the strength of an answer we never
        # got. Nothing about this order is decided until Ziina actually says something.
        raise HTTPException(status_code=502, detail="Ziina did not say what happened to the payment")
    return pi
