// Fixed delivery destinations (UAE emirates). The customer picks one instead of
// typing a free-form city, so the delivery fee maps to a known value every time.
// `value` (Arabic) is what gets stored and matched against zone keywords.
export const EMIRATES = [
  { value: 'أبو ظبي', en: 'Abu Dhabi' },
  { value: 'دبي', en: 'Dubai' },
  { value: 'الشارقة', en: 'Sharjah' },
  { value: 'عجمان', en: 'Ajman' },
  { value: 'أم القيوين', en: 'Umm Al Quwain' },
  { value: 'رأس الخيمة', en: 'Ras Al Khaimah' },
  { value: 'الفجيرة', en: 'Fujairah' },
  { value: 'العين', en: 'Al Ain' },
]

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
