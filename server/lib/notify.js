// New-order notifications to the manager's WhatsApp via CallMeBot (free).
// Configure with env WHATSAPP_PHONE + WHATSAPP_APIKEY (see DEPLOY.md).

// Low-level send. Returns { configured, ok, error } and never throws.
async function sendWhatsApp(text) {
  const phone = process.env.WHATSAPP_PHONE
  const apikey = process.env.WHATSAPP_APIKEY
  if (!phone || !apikey) return { configured: false, ok: false, error: 'WHATSAPP_PHONE / WHATSAPP_APIKEY not set' }

  const url =
    `https://api.callmebot.com/whatsapp.php?phone=${encodeURIComponent(phone)}` +
    `&text=${encodeURIComponent(text)}&apikey=${encodeURIComponent(apikey)}`
  try {
    const res = await fetch(url)
    const body = await res.text().catch(() => '')
    if (!res.ok) {
      console.error('[notify] whatsapp failed:', res.status, body.slice(0, 200))
      return { configured: true, ok: false, error: `HTTP ${res.status}`, detail: body.slice(0, 300) }
    }
    return { configured: true, ok: true }
  } catch (e) {
    console.error('[notify] whatsapp error:', e.message)
    return { configured: true, ok: false, error: e.message }
  }
}

export async function notifyNewOrder(order) {
  const items = (order.items || []).map((i) => `${i.name} ×${i.qty}`).join('، ')
  const text =
    `🛒 طلبٌ جديد #${String(order.id).slice(0, 8)}\n` +
    `${order.customer_name} · ${order.phone}\n` +
    `${order.city}، ${order.street}، ${order.house}\n` +
    `${items}\n` +
    `المجموع: ${order.total}`
  return sendWhatsApp(text)
}

export async function sendTestNotification() {
  return sendWhatsApp('🔔 دكّان كنعان — هذه رسالة اختبار. الإشعارات تعمل ✅')
}
