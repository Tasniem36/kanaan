// Validate a UAE mobile number and return it normalized as +9715XXXXXXXX, or null.
// Accepts 05XXXXXXXX, 5XXXXXXXX, 9715XXXXXXXX, +9715XXXXXXXX (spaces/dashes ok).
export function normalizeUaePhone(raw) {
  let d = String(raw || '').replace(/\D/g, '')
  if (d.startsWith('971')) d = d.slice(3)
  else if (d.startsWith('0')) d = d.slice(1)
  return /^5\d{8}$/.test(d) ? '+971' + d : null
}
