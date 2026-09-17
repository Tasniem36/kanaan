// Fire-and-forget error reporting to the admin error log. Uses a raw fetch (NOT the
// api wrapper) so a failing report can never trigger more reports (no recursion),
// and never throws.
let last = 0

// Noise we never want in the log: scripts injected by Instagram/Facebook in-app
// browsers (they error on their own, our site is fine), benign browser warnings,
// and stale-chunk errors (handled by an auto-reload in the router instead).
const IGNORE = [
  // Opaque cross-origin error — carries no file/line/stack (detail is just ":").
  // Almost always a third-party/ad script inside a social in-app browser, not us.
  'Script error.',
  'webkit.messageHandlers',
  'postMessage: Java object is gone',
  'iabjs://',
  'navigation_performance_logger',
  'Failed to fetch dynamically imported module',
  'Importing a module script failed',
  'error loading dynamically imported module',
  'ResizeObserver loop',
]

// Extension schemes. An extension's content script runs in the page and its throws
// reach window.onerror looking like ours, but no origin comparison catches them —
// some browsers report these URLs with a null origin, which is also what a blob:
// worker of our own reports.
const EXTENSION = /^(chrome|moz|safari|safari-web|ms-browser)-extension:$/

// Whether an onerror filename belongs to a script we did not ship.
//
// window.onerror fires for every script on the page, including ones we never put
// there: browser extensions' content scripts, and the analytics and ad scripts that
// the Instagram and Facebook in-app browsers inject into whatever they open. Those
// fail on their own schedule while the shop is working perfectly, and each one costs
// the manager a row to read and decide about.
//
// The test is "provably somebody else's", not "not under /assets/". Same-origin is
// more than the bundles — the service worker, and anything inline in a prerendered
// page, whose filename is the page's own URL — and an error we cannot place is kept
// rather than dropped. A missed drop is one noisy row; a wrong drop is a customer
// stuck on a blank screen that nobody ever hears about. So: only a real http(s)
// origin that differs from ours, or an extension URL. Everything else — blob:,
// data:, about:, a filename that won't parse, no filename at all — is treated as
// ours and reported. ('Script error.', the opaque cross-origin case that carries no
// filename to judge, is already dropped by IGNORE above.)
export function isForeignScript(filename) {
  const src = String(filename || '').trim()
  if (!src) return false
  try {
    const url = new URL(src, window.location.href)
    if (EXTENSION.test(url.protocol)) return true
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return false
    return url.origin !== window.location.origin
  } catch {
    return false   // unparseable — we can't prove it isn't ours
  }
}

export function reportError(message, detail) {
  try {
    if (typeof window === 'undefined') return
    const text = `${message || ''} ${detail || ''}`
    if (IGNORE.some((p) => text.includes(p))) return   // third-party / handled noise
    const now = Date.now()
    if (now - last < 1500) return   // throttle bursts
    last = now
    const token = localStorage.getItem('token')
    fetch('/api/errors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({
        message: String(message || 'error').slice(0, 1000),
        detail: detail ? String(detail).slice(0, 4000) : undefined,
        page: window.location.pathname + window.location.search,
      }),
      keepalive: true,
    }).catch(() => {})
  } catch { /* never throw */ }
}
