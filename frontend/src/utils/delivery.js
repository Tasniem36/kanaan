// Mirror of backend delivery.py: Abu Dhabi / Al Ain = fee_high, else fee_low;
// free when subtotal reaches free_threshold (0 disables it). Emirate is detected
// from the free-text city. The backend recomputes this authoritatively.
const HIGH = ['ابوظبي', 'العين', 'abudhabi', 'alain']

function norm(s) {
  return (s || '').trim().toLowerCase().replace(/\s+/g, '').replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي')
}

export function deliveryFee(city, subtotal, cfg) {
  const thr = Number(cfg?.free_threshold)
  if (thr > 0 && Number(subtotal) >= thr) return 0
  const n = norm(city)
  const high = HIGH.some((k) => n.includes(k))
  return Number(high ? (cfg?.fee_high ?? 30) : (cfg?.fee_low ?? 25))
}
