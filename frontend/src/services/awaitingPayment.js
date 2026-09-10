// The one order whose payment we never got an answer about.
//
// PayReturn stops polling after a few seconds and, when Ziina still hasn't resolved
// the intent, ends on "we don't know yet" with the basket left alone — the basket only
// ever empties on a confirmed success. backend/reconcile.py settles the order minutes
// later, but by then the browser is gone: the customer reads the WhatsApp confirmation
// and comes back to a basket still holding what they have just paid for.
//
// So the order is noted here, and the next app load asks once how it ended. Paid takes
// that order's lines out of the basket — the same rule as everywhere else, applied to a
// success we learned about late. Anything else leaves it exactly where it was.
import { api } from './api'

const KEY = 'awaiting_payment'
// Past this nobody is coming back to a basket from that visit anyway, and the sweep
// stops looking too (LOOKBACK_DAYS in reconcile.py). Keeps a token that never resolved
// from being re-asked about for the life of the browser profile.
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

function read() {
  if (import.meta.env.SSR) return null
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (!saved?.id || !saved?.token) return null
    return Date.now() - new Date(saved.at).getTime() < MAX_AGE_MS ? saved : null
  } catch {
    return null
  }
}

export function rememberAwaited(id, token) {
  if (import.meta.env.SSR || !id || !token) return
  try {
    localStorage.setItem(KEY, JSON.stringify({ id, token, at: new Date().toISOString() }))
  } catch { /* storage full or blocked — we just won't catch up on the next load */ }
}

export function forgetAwaited() {
  if (import.meta.env.SSR) return
  try {
    localStorage.removeItem(KEY)
  } catch { /* nothing to do about it */ }
}

// Costs one request, and only for someone who actually left a payment hanging.
export async function settleAwaited(cart) {
  const awaited = read()
  if (!awaited) return forgetAwaited()  // absent, malformed, or too old to matter
  let order
  try {
    ;({ order } = await api(`/orders/track/${awaited.id}?t=${encodeURIComponent(awaited.token)}`, { auth: true }))
  } catch (e) {
    // 404: the order is gone or the token no longer opens it, so there is nothing left
    // to wait for. Anything else (offline, a 500) keeps the note for the next load.
    if (e.status === 404) forgetAwaited()
    return
  }
  if (order.payment_status === 'paid') {
    // The boot pull of the server cart is in flight beside this one. It merges keeping
    // the larger quantity per product, so removing these lines before it lands has
    // them put right back — and saved to the server, leaving a signed-in customer
    // staring at a basket full of what they have already paid for.
    await cart.whenSynced()
    // Only what this order paid for. Up to a week can pass between the payment and
    // this answer (MAX_AGE_MS), and emptying the basket wholesale would take out
    // everything added in between.
    cart.removeOrdered(order.items)
    forgetAwaited()
  } else if (order.status === 'cancelled') {
    forgetAwaited()  // the sweep released it; the basket stays, so they can try again
  }
  // still unresolved: reconcile.py hasn't reached it yet — ask again next time
}
