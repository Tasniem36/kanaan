// Minimal Ziina Payments client. Docs: https://docs.ziina.com/api-reference/payment-intent
const BASE = 'https://api-v2.ziina.com/api'

function authHeader() {
  const key = process.env.ZIINA_API_KEY
  if (!key) throw { status: 500, message: 'Ziina غير مُهيّأ على الخادم' }
  return { Authorization: `Bearer ${key}` }
}

// amountFils: integer in fils (100 AED = 10000). Returns { id, redirect_url, status, ... }
export async function createPaymentIntent({ amountFils, successUrl, cancelUrl, message }) {
  const res = await fetch(`${BASE}/payment_intent`, {
    method: 'POST',
    headers: { ...authHeader(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      amount: amountFils,
      currency_code: 'AED',
      message,
      success_url: successUrl,
      cancel_url: cancelUrl,
      failure_url: cancelUrl,
      test: process.env.ZIINA_TEST === 'true',
    }),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw { status: 502, message: data?.message || 'تعذّر إنشاء الدفعة عبر Ziina' }
  return data
}

// Returns the payment intent (status: requires_payment_instrument | pending |
// requires_user_action | completed | failed)
export async function getPaymentIntent(id) {
  const res = await fetch(`${BASE}/payment_intent/${id}`, { headers: authHeader() })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw { status: 502, message: data?.message || 'تعذّر التحقق من الدفعة' }
  return data
}
