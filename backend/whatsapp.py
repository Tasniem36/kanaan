"""Customer-facing WhatsApp, via Meta's WhatsApp Business Cloud API.

Not to be confused with the WhatsApp sender in notify.py. That one goes through
CallMeBot to the shop's *own* number to announce new orders, and can only reach a
number that has already messaged the bot — no use for writing to a customer. Reaching
a customer needs the Cloud API, and a message the shop starts (rather than a reply
inside a 24-hour window) has to be an approved template. Hence the template names
below rather than free text.

Why it exists: a guest who leaves no e-mail address has no channel at all. The order
carries a phone number — it has to, the shop delivers to it — so WhatsApp is the one
way to tell them anything. See routers/orders.py.

Never raises. A shop whose messaging is misconfigured still takes orders.

Configure with:
  WA_CLOUD_TOKEN       — permanent access token for the WhatsApp Business app
  WA_CLOUD_PHONE_ID    — the sender's phone number ID (not the phone number)
  WA_TEMPLATE_PLACED   — template name for the order confirmation  (default order_placed)
  WA_TEMPLATE_STATUS   — template name for a status change         (default order_status)
  WA_TEMPLATE_LANG     — template language code                    (default ar)
  WA_NOTIFY_ALL        — 'true' to message every customer, not only those with no
                         other channel. Off by default: account holders already get
                         the in-app notification and the push, and each template
                         message is billed.
Unset WA_CLOUD_TOKEN / WA_CLOUD_PHONE_ID and every call here is a no-op.
"""
import os

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def _config():
    token = os.getenv("WA_CLOUD_TOKEN")
    phone_id = os.getenv("WA_CLOUD_PHONE_ID")
    return (token, phone_id) if token and phone_id else None


def configured() -> bool:
    return _config() is not None


def notify_all() -> bool:
    """Whether to message customers who already have another channel."""
    return (os.getenv("WA_NOTIFY_ALL") or "").lower() == "true"


def _to_msisdn(phone: str) -> str:
    """Cloud API wants digits only, country code included, no '+'."""
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _send_template(phone: str, template: str, params: list[str]) -> dict:
    cfg = _config()
    if not cfg:
        return {"configured": False, "ok": False, "error": "WA_CLOUD_TOKEN / WA_CLOUD_PHONE_ID not set"}
    token, phone_id = cfg
    to = _to_msisdn(phone)
    if not to:
        return {"configured": True, "ok": False, "error": "no phone number on the order"}
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": os.getenv("WA_TEMPLATE_LANG") or "ar"},
            "components": [{
                "type": "body",
                # every parameter is positional: {{1}}, {{2}}, … in the approved body
                "parameters": [{"type": "text", "text": str(p)} for p in params],
            }],
        },
    }
    try:
        res = requests.post(
            f"{GRAPH}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=20,
        )
    except requests.RequestException as e:
        print("[whatsapp] error:", e)
        return {"configured": True, "ok": False, "error": str(e)}
    try:
        data = res.json() if res.content else {}
    except ValueError:
        # a proxy or gateway answering with an HTML error page, not Meta
        data = {}
    if not res.ok:
        # the message that matters is Meta's: a template not yet approved, a number
        # outside the allowed list on a trial app, an expired token
        err = ((data.get("error") or {}).get("message")) or f"HTTP {res.status_code}"
        print("[whatsapp] send failed:", res.status_code, err)
        return {"configured": True, "ok": False, "error": err}
    return {"configured": True, "ok": True, "id": (data.get("messages") or [{}])[0].get("id")}


def send_order_placed(*, phone, number, total, track_url) -> dict:
    """The confirmation. Carries the order number and the tracking link, so the guest
    keeps a copy of both somewhere they won't lose — which the screen alone isn't."""
    return _send_template(phone, os.getenv("WA_TEMPLATE_PLACED") or "order_placed",
                          [str(number), str(total), str(track_url)])


def send_order_status(*, phone, number, status_label, track_url) -> dict:
    """An order moved. The whole point of the exercise."""
    return _send_template(phone, os.getenv("WA_TEMPLATE_STATUS") or "order_status",
                          [str(number), str(status_label), str(track_url)])
