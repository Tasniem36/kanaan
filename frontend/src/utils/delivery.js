// Mirror of backend delivery.py: a city matching a zone's keywords pays that
// zone's fee; otherwise default_fee; free when subtotal reaches free_threshold
// (0 disables). The backend recomputes this authoritatively at checkout.
function norm(s) {
  return (s || '').trim().toLowerCase().replace(/\s+/g, '').replace(/[أإآ]/g, 'ا').replace(/ى/g, 'ي')
}

export function deliveryFee(city, subtotal, cfg) {
  const thr = Number(cfg?.free_threshold)
  if (thr > 0 && Number(subtotal) >= thr) return 0
  const n = norm(city)
  for (const z of cfg?.zones || []) {
    const kws = String(z.keywords || '').split(',').map((k) => norm(k)).filter(Boolean)
    if (kws.some((k) => n.includes(k))) return Number(z.fee)
  }
  return Number(cfg?.default_fee ?? 25)
}
