import { createI18n } from 'vue-i18n'
import ar from './ar'
import en from './en'

const RTL = ['ar']
// During prerender there's no localStorage; default to Arabic (matches the static
// lang/dir in index.html), then the client reads the saved locale on load.
const saved = (!import.meta.env.SSR && localStorage.getItem('locale')) || 'ar'

// Arabic counts a noun six different ways, and vue-i18n's built-in rule only knows
// the English two — so "1 رأيًا" instead of "رأيٌ واحد". Message order is
// zero | one | two | few (3–10) | many (11–99) | other (100, 200, …), per CLDR.
function arabicPlural(choice) {
  if (choice === 0) return 0
  if (choice === 1) return 1
  if (choice === 2) return 2
  const mod100 = choice % 100
  if (mod100 >= 3 && mod100 <= 10) return 3
  if (mod100 >= 11) return 4
  return 5
}

export const i18n = createI18n({
  legacy: false,
  locale: saved,
  fallbackLocale: 'ar',
  messages: { ar, en },
  pluralRules: { ar: arabicPlural },
})

// Reflect the active locale on <html lang/dir> so layout flips RTL ↔ LTR.
export function applyDir(locale = i18n.global.locale.value) {
  if (import.meta.env.SSR) return
  document.documentElement.lang = locale
  document.documentElement.dir = RTL.includes(locale) ? 'rtl' : 'ltr'
}

export function setLocale(locale) {
  i18n.global.locale.value = locale
  if (!import.meta.env.SSR) localStorage.setItem('locale', locale)
  applyDir(locale)
}

if (!import.meta.env.SSR) applyDir() // sync on load (client only)
