"""New-order WhatsApp notifications via CallMeBot (free). Configure with
WHATSAPP_PHONE + WHATSAPP_APIKEY. Never raises."""
import os

import requests


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


def notify_new_order(order: dict) -> dict:
    items = "، ".join(f"{i['name']} ×{i['qty']}" for i in order.get("items", []))
    text = (
        f"🛒 طلبٌ جديد #{str(order['id'])[:8]}\n"
        f"{order['customer_name']} · {order['phone']}\n"
        f"{order['city']}، {order['street']}، {order['house']}\n"
        f"{items}\n"
        f"المجموع: {order['total']}"
    )
    return _send_whatsapp(text)


def send_test_notification() -> dict:
    return _send_whatsapp("🔔 دكّان كنعان — هذه رسالة اختبار. الإشعارات تعمل ✅")
