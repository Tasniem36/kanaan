// Fire-and-forget error reporting to the admin error log. Uses a raw fetch (NOT the
// api wrapper) so a failing report can never trigger more reports (no recursion),
// and never throws.
let last = 0

export function reportError(message, detail) {
  try {
    if (typeof window === 'undefined') return
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
