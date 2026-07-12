// Server-side validation — the source of truth (the browser checks are UX only).
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
// strong password: ≥8 chars with at least one uppercase, one lowercase, one digit
export const STRONG_PW_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/

// Validate a UAE mobile and return it normalized as +9715XXXXXXXX, or null.
export function normalizeUaePhone(raw) {
  let d = String(raw || '').replace(/\D/g, '')
  if (d.startsWith('971')) d = d.slice(3)
  else if (d.startsWith('0')) d = d.slice(1)
  return /^5\d{8}$/.test(d) ? '+971' + d : null
}
