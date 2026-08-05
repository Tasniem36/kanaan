"""Web Push (device notifications). Sends to a user's subscribed browsers via the
Web Push protocol (VAPID). Best-effort and fire-and-forget: runs in a thread, never
raises, and prunes dead subscriptions. No-op unless VAPID keys are configured.

Configure:  VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY (base64url raw keys), VAPID_SUBJECT.
"""
import json
import os
import threading

from db import fetch_all, execute

_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@dukkan-kanaan.com")
_PRIVATE = os.getenv("VAPID_PRIVATE_KEY")
_PUBLIC = os.getenv("VAPID_PUBLIC_KEY")


def public_key():
    return _PUBLIC


def configured():
    return bool(_PRIVATE and _PUBLIC)


def _vapid():
    from py_vapid import Vapid01
    return Vapid01.from_raw(private_raw=_PRIVATE.encode())


def _worker(user_ids, payload):
    from pywebpush import webpush, WebPushException
    subs = fetch_all(
        "select id, endpoint, p256dh, auth from push_subscriptions where user_id = any(%s::uuid[])",
        [user_ids],
    )
    if not subs:
        return
    vapid = _vapid()
    for s in subs:
        info = {"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}}
        try:
            webpush(info, payload, vapid_private_key=vapid, vapid_claims={"sub": _SUBJECT}, ttl=86400)
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):  # subscription expired/gone → remove it
                execute("delete from push_subscriptions where id = %s", [s["id"]])
            else:
                print("[push] send failed:", code, str(e)[:200])
        except Exception as e:  # noqa: BLE001
            print("[push] error:", str(e)[:200])


def push_to_users(user_ids, *, title, body=None, url="/", tag="dukkan"):
    """Fire a device notification to every subscribed browser of these users."""
    if not configured():
        return
    ids = [str(u) for u in user_ids if u]
    if not ids:
        return
    payload = json.dumps({"title": title, "body": body or "", "url": url, "tag": tag})
    threading.Thread(target=_safe, args=(ids, payload), daemon=True).start()


def _safe(ids, payload):
    try:
        _worker(ids, payload)
    except Exception as e:  # noqa: BLE001 — never let push break anything
        print("[push] worker error:", str(e)[:200])
