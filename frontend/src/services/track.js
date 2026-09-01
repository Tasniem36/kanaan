// Storefront moments only the browser knows about, reported to the activity log.
//
// The server can't see these: a basket lives in the browser until checkout, a search
// is indistinguishable from browsing the catalogue, and a shopper sent to sign in
// never reaches an endpoint at all. The server whitelists both the event names and
// the fields each may carry (backend/routers/audit.py), so nothing here is trusted —
// this only decides *when* to speak.
//
// Fire and forget: the log is never worth a spinner, an error, or a delay in front of
// what the customer was doing.
import { api } from './api'

export function track(event, detail) {
  if (typeof window === 'undefined') return   // never during prerender
  api('/audit/event', { method: 'POST', body: { event, detail } }).catch(() => {})
}
