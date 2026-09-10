"""New-order notifications. Sends to every configured channel:
  - Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (reliable, free).
    TELEGRAM_CHAT_ID takes one id or several, comma-separated.
  - WhatsApp via CallMeBot: WHATSAPP_PHONE + WHATSAPP_APIKEY (free, best-effort)
Never raises."""
import os

import requests

try:
    from zoneinfo import ZoneInfo
    _DUBAI_TZ = ZoneInfo("Asia/Dubai")   # order times shown in the shop's local time
except Exception:
    _DUBAI_TZ = None


def _telegram_chat_ids() -> list:
    """The recipients in TELEGRAM_CHAT_ID: one id, or several separated by commas.
    A repeated id is dropped — it would only alert the same person twice per order."""
    ids = []
    for part in (os.getenv("TELEGRAM_CHAT_ID") or "").split(","):
        chat_id = part.strip()
        if chat_id and chat_id not in ids:
            ids.append(chat_id)
    return ids


def _send_telegram_to(token: str, chat_id: str, text: str) -> dict:
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
        if not res.ok:
            print(f"[notify] telegram failed for {chat_id}:", res.status_code, res.text[:200])
            return {"ok": False, "error": f"HTTP {res.status_code}", "detail": res.text[:300]}
        return {"ok": True}
    except Exception as e:
        print(f"[notify] telegram error for {chat_id}:", e)
        return {"ok": False, "error": str(e)}


def _send_telegram(text: str) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = _telegram_chat_ids()
    if not token or not chat_ids:
        return {"configured": False, "ok": False, "error": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"}
    # Every recipient is tried, whatever the ones before them did: a single bad id
    # (someone who never pressed Start, a bot removed from the channel) must not
    # swallow the alert for everyone else.
    recipients = {cid: _send_telegram_to(token, cid, text) for cid in chat_ids}
    failed = {cid: r for cid, r in recipients.items() if not r["ok"]}
    out = {"configured": True, "ok": len(failed) < len(recipients), "recipients": recipients}
    if failed:
        out["error"] = "; ".join(f"{cid}: {r['error']}" for cid, r in failed.items())
    return out


def _send_whatsapp(text: str) -> dict:
    phone = os.getenv("WHATSAPP_PHONE")
    apikey = os.getenv("WHATSAPP_APIKEY")
    if not phone or not apikey:
        return {"configured": False, "ok": False, "error": "WHATSAPP_PHONE / WHATSAPP_APIKEY not set"}
    try:
        res = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": phone, "text": text, "apikey": apikey},
            timeout=20,
        )
        if not res.ok:
            print("[notify] whatsapp failed:", res.status_code, res.text[:200])
            return {"configured": True, "ok": False, "error": f"HTTP {res.status_code}", "detail": res.text[:300]}
        return {"configured": True, "ok": True}
    except Exception as e:
        print("[notify] whatsapp error:", e)
        return {"configured": True, "ok": False, "error": str(e)}


def _send(text: str) -> dict:
    """Send to every configured channel. ok=True if any configured channel succeeded."""
    results = {"telegram": _send_telegram(text), "whatsapp": _send_whatsapp(text)}
    configured = {k: v for k, v in results.items() if v.get("configured")}
    return {
        "configured": bool(configured),
        "ok": any(v.get("ok") for v in configured.values()),
        "channels": results,
    }


def _payment_line(order: dict) -> str:
    method = "بطاقة (Ziina)" if order.get("payment_method") == "ziina" else "عند الاستلام (COD)"
    paid = order.get("payment_status") == "paid"
    return f"💳 الدفع: {method} — {'مدفوع ✅' if paid else 'غير مدفوع ⏳'}"


def _order_time(order: dict) -> str:
    t = order.get("created_at")
    if not t:
        return ""
    try:
        if isinstance(t, str):
            return t
        dt = t.astimezone(_DUBAI_TZ) if _DUBAI_TZ else t
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(t)


def notify_new_order(order: dict) -> dict:
    items = "، ".join(f"{i['name']} ×{i['qty']}" for i in order.get("items", []))
    when = _order_time(order)
    text = (
        f"🛒 طلبٌ جديد #{str(order['id'])[:8]}\n"
        f"{order['customer_name']} · {order['phone']}\n"
        f"{order['city']}، {order['street']}، {order['house']}\n"
        f"{items}\n"
        f"المجموع: {order['total']}\n"
        f"{_payment_line(order)}"
        + (f"\n🕒 {when}" if when else "")
    )
    return _send(text)

