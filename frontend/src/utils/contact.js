// How a customer reaches the shop. One source, because these appear in the footer,
// in the help panel a stuck customer is shown, and in the order confirmation e-mail —
// and a phone number that disagrees with itself across a site is worse than one that
// is only in a single place.
//
// WHATSAPP_DIGITS is what wa.me wants: international digits, no '+' and no spaces.
// WHATSAPP_DISPLAY is the same number written the way somebody would read it aloud.
export const WHATSAPP_DIGITS = '971522981187'
export const WHATSAPP_DISPLAY = '+971 52 298 1187'
export const EMAIL = 'dukkan.kanaan@gmail.com'
export const INSTAGRAM = 'dukkan_kanaan'

// `text` prefills the message box, so a customer arrives with their problem already
// written down instead of having to explain it from scratch.
export function whatsappLink(text) {
  const base = `https://wa.me/${WHATSAPP_DIGITS}`
  return text ? `${base}?text=${encodeURIComponent(text)}` : base
}

export function emailLink(subject) {
  return subject ? `mailto:${EMAIL}?subject=${encodeURIComponent(subject)}` : `mailto:${EMAIL}`
}
