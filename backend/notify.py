"""New-order notifications. Sends to every configured channel:
  - Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (reliable, free)
  - WhatsApp via CallMeBot: WHATSAPP_PHONE + WHATSAPP_APIKEY (free, best-effort)
Never raises."""
import os

import requests


def _send_telegram(text: str) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"configured": False, "ok": False, "error": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"}
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
        if not res.ok:
            print("[notify] telegram failed:", res.status_code, res.text[:200])
            return {"configured": True, "ok": False, "error": f"HTTP {res.status_code}", "detail": res.text[:300]}
        return {"configured": True, "ok": True}
    except Exception as e:
        print("[notify] telegram error:", e)
        return {"configured": True, "ok": False, "error": str(e)}


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


def notify_new_order(order: dict) -> dict:
    items = "، ".join(f"{i['name']} ×{i['qty']}" for i in order.get("items", []))
    text = (
        f"🛒 طلبٌ جديد #{str(order['id'])[:8]}\n"
        f"{order['customer_name']} · {order['phone']}\n"
        f"{order['city']}، {order['street']}، {order['house']}\n"
        f"{items}\n"
        f"المجموع: {order['total']}"
    )
    return _send(text)


def send_test_notification() -> dict:
    return _send("🔔 دكّان كنعان — هذه رسالة اختبار. الإشعارات تعمل ✅")
