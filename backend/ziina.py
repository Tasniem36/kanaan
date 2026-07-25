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
    data = res.json() if res.content else {}
    if not res.ok:
        raise HTTPException(status_code=502, detail=data.get("message") or "Could not create the Ziina payment")
    return data


def get_payment_intent(pid):
    try:
        res = requests.get(f"{BASE}/payment_intent/{pid}", headers=_headers(), timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Could not verify the payment: {e}")
    data = res.json() if res.content else {}
    if not res.ok:
        raise HTTPException(status_code=502, detail=data.get("message") or "Could not verify the payment")
    pi = data.get("payment_intent") or data.get("result") or data or {}
    print("[ziina] intent", pid, "status =", pi.get("status"), "| keys:", ",".join(data.keys()))
    return pi
