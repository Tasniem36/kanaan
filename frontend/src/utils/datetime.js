// Every time this shop shows is the shop's own time.
//
// Left to itself, toLocaleString renders in whatever timezone the device happens to
// be set to. That is right for a calendar and wrong for a shop: an order placed at
// 16:00 was placed at 16:00, and it should read that way to the manager checking it
// from abroad, on the dashboard, in the Telegram alert and on the customer's tracking
// page alike. Those last two are already fixed to Asia/Dubai server-side (notify.py,
// routers/stats.py bucket the day the same way), so anything left on device time
// would simply disagree with them.
//
// The browser carries the full IANA database, so naming the zone costs nothing and
// needs no data shipped with the app. The UAE has never observed DST, but the named
// zone is still better than a hardcoded +04:00 — if that ever changes, this follows.
export const SHOP_TZ = 'Asia/Dubai'

const fmt = (d, locale, opts) => {
  if (!d) return ''
  const at = new Date(d)
  if (Number.isNaN(at.getTime())) return ''
  return at.toLocaleString(locale || 'ar', { timeZone: SHOP_TZ, ...opts })
}

// 10 Sept 2026, 16:00 — the default for anything with a clock on it
export const dateTime = (d, locale) => fmt(d, locale, { dateStyle: 'medium', timeStyle: 'short' })

// 10 Sep, 16:00 — tighter, for lists and timelines
export const dayTime = (d, locale) =>
  fmt(d, locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

// 10 Sep — an axis label, no clock
export const dayMonth = (d, locale) => fmt(d, locale, { day: 'numeric', month: 'short' })

// 10 September 2026 — a date said in full, where there is room for it
export const longDate = (d, locale) =>
  fmt(d, locale, { year: 'numeric', month: 'long', day: 'numeric' })
