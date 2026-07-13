// Fire-and-forget new-order notification to the manager's WhatsApp.
// Uses CallMeBot (free, one-time opt-in — see DEPLOY.md "WhatsApp alerts").
// No-op unless WHATSAPP_PHONE and WHATSAPP_APIKEY are set, and never throws
// (a notification failure must not break order placement).
export async function notifyNewOrder(order) {
  const phone = process.env.WHATSAPP_PHONE
  const apikey = process.env.WHATSAPP_APIKEY
  if (!phone || !apikey) return

  const items = (order.items || []).map((i) => `${i.name} ×${i.qty}`).join('، ')
  const text =
    `🛒 طلبٌ جديد #${String(order.id).slice(0, 8)}\n` +
    `${order.customer_name} · ${order.phone}\n` +
    `${order.city}، ${order.street}، ${order.house}\n` +
    `${items}\n` +
    `المجموع: ${order.total}`

  const url =
    `https://api.callmebot.com/whatsapp.php?phone=${encodeURIComponent(phone)}` +
    `&text=${encodeURIComponent(text)}&apikey=${encodeURIComponent(apikey)}`

  try {
    const res = await fetch(url)
    if (!res.ok) console.error('[notify] whatsapp failed:', res.status)
  } catch (e) {
    console.error('[notify] whatsapp error:', e.message)
  }
}
