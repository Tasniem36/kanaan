// Fire-and-forget error reporting to the admin error log. Uses a raw fetch (NOT the
// api wrapper) so a failing report can never trigger more reports (no recursion),
// and never throws.
let last = 0

// Noise we never want in the log: scripts injected by Instagram/Facebook in-app
// browsers (they error on their own, our site is fine), benign browser warnings,
// and stale-chunk errors (handled by an auto-reload in the router instead).
const IGNORE = [
  'webkit.messageHandlers',
  'postMessage: Java object is gone',
  'iabjs://',
  'navigation_performance_logger',
  'Failed to fetch dynamically imported module',
  'Importing a module script failed',
  'error loading dynamically imported module',
  'ResizeObserver loop',
]

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
