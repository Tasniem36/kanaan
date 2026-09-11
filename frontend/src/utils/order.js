// One reading of an order, for every page that shows one to its customer.
//
// The tracking page and طلباتي used to answer these questions separately, and had
// already drifted: an unpaid order counted as awaiting payment when payment_method
// was `!== 'cod'` on one page and `=== 'ziina'` on the other, so anything that was
// neither had the two screens telling the same customer different things about the
// same order. The same split had grown in the status label, in two sets of
// translations for one meaning, and in whether the money was formatted at all.
//
// The backend writes exactly 'ziina' or 'cod' (routers/orders.py normalises on the
// way in) and reads it back as `== 'ziina'` everywhere — reconcile.py, notify.py,
// the refund path — so that is the test used here too.
export const isOnline = (o) => o?.payment_method === 'ziina'

// What the customer was told to quote: the number on the confirmation e-mail, on the
// WhatsApp, and the one the lookup form asks for. The id prefix is only the fallback
// for orders placed before ref existed — the same fallback as display_ref() server
// side, so a customer and the shop never hold two different names for one order.
export const orderNumber = (o) =>
  o?.number || (o?.ref ? `DK-${o.ref}` : `#${String(o?.id || '').slice(0, 8)}`)

// Money in the digits of the page it's on — ٦٥ under ar, 65 under en.
export const money = (n, locale) =>
  new Intl.NumberFormat(locale === 'ar' ? 'ar-AE' : 'en-AE', { maximumFractionDigits: 2 })
    .format(Number(n || 0))

// An online order nobody has paid for, and still alive. Cash is unpaid by definition
// until it is handed over, and a cancelled order has had its stock put back — neither
// is money for a status page to collect.
export const isAwaitingPayment = (o) => !!o
  && isOnline(o) && o.payment_status !== 'paid' && o.status !== 'cancelled'

// Released for not being paid for, rather than cancelled by anybody. Worth saying out
// loud wherever it shows: the first thing a customer thinks on reading "cancelled" is
// whether they have been charged for it.
export const isReleasedUnpaid = (o) => !!o
  && isOnline(o) && o.status === 'cancelled' && o.payment_status !== 'paid'

// What actually happened to the money — read from the payment fields alone, never
// inferred from how far the order has travelled. The wording is the confirmation
// e-mail's (_order_email in routers/orders.py), so the two agree.
export function payLabelKey(o) {
  if (!o) return ''
  if (!isOnline(o)) return o.status === 'delivered' ? 'track.paidOnDelivery' : 'checkout.cod'
  if (o.payment_status === 'paid') return 'track.paidOnline'
  // Nobody is awaiting payment for an order the shop has taken the goods back on;
  // next to a red ملغى that reads as a bill still owed.
  return o.status === 'cancelled' ? 'track.notPaid' : 'track.awaitingPayment'
}

// 'pending' means two different things: a cash order being processed, and a card
// order still waiting to be paid for. OrderTimeline draws the same distinction.
export const statusLabelKey = (o) =>
  (o?.status === 'pending' && !isOnline(o) ? 'status.pendingCod' : `status.${o?.status}`)
