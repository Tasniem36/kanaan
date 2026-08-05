"""Web Push subscription management. The browser subscribes with the VAPID public
key and posts its subscription here; we store it per user and send to it later."""
from fastapi import APIRouter, Body, Depends, HTTPException

from db import execute, fetch_one
from security import current_user
import push

router = APIRouter()


@router.get("/key")
def vapid_key():
    # public — the browser needs this to subscribe
    return {"key": push.public_key()}


@router.post("/subscribe")
def subscribe(user=Depends(current_user), payload: dict = Body(default={})):
    sub = payload.get("subscription") or payload
    endpoint = sub.get("endpoint")
    keys = sub.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not endpoint or not p256dh or not auth:
        raise HTTPException(400, "Invalid subscription")
    # upsert by endpoint (re-subscribing / switching account on the same browser)
    execute(
        """insert into push_subscriptions (user_id, endpoint, p256dh, auth)
           values (%s, %s, %s, %s)
           on conflict (endpoint) do update set user_id = excluded.user_id,
             p256dh = excluded.p256dh, auth = excluded.auth""",
        [user["id"], endpoint, p256dh, auth],
    )
    return {"ok": True}


@router.post("/unsubscribe")
def unsubscribe(user=Depends(current_user), payload: dict = Body(default={})):
    endpoint = (payload.get("subscription") or payload).get("endpoint")
    if endpoint:
        execute("delete from push_subscriptions where endpoint = %s", [endpoint])
    return {"ok": True}
