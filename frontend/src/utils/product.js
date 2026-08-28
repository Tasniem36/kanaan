// Localised product text.
//
// Products store Arabic in the base columns (name, description, unit, tag) and
// English in the *_en ones. English is only used when it's actually filled in —
// a product the manager hasn't translated yet still reads correctly in Arabic
// rather than showing a blank name. Mirrors how content_values is rendered on
// the home page.
import { i18n } from '../i18n'

function pick(ar, en) {
  if (i18n.global.locale.value !== 'ar') {
    const t = typeof en === 'string' ? en.trim() : ''
    if (t) return t
  }
  return ar || ''
}

// --- price ---
// A product on offer keeps its usual price and carries a sale_price beside it. What
// the shopper pays is the offer when there is one — the server charges the same way
// (routers/orders.py), so these agree by construction rather than by luck.
export const pIsOnSale = (p) => Number(p?.sale_price) > 0 && Number(p.sale_price) < Number(p.price)
export const pPrice = (p) => Number(pIsOnSale(p) ? p.sale_price : p?.price || 0)
// How much off, as a whole percent — what the badge on the corner of the card says
export const pSaleOff = (p) => (pIsOnSale(p) ? Math.round((1 - p.sale_price / p.price) * 100) : 0)

// How an offer price reads against the price it discounts. Shared by the add and the
// edit dialogs so the manager is told the same thing in both — and it matches what
// the server will accept (routers/products._sale_price).
export function saleState(sale, price) {
  if (sale === '' || sale === null || sale === undefined) return { kind: 'none' }
  const s = Number(sale)
  const p = Number(price)
  if (!(s > 0 && s < p)) return { kind: 'bad' }
  return { kind: 'on', off: Math.round((1 - s / p) * 100) }
}

export const pName = (p) => (p ? pick(p.name, p.name_en) : '')
export const pDesc = (p) => (p ? pick(p.description, p.description_en) : '')
export const pUnit = (p) => (p ? pick(p.unit, p.unit_en) : '')
export const pTag = (p) => (p ? pick(p.tag, p.tag_en) : '')
