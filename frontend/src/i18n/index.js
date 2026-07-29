import { createI18n } from 'vue-i18n'
import ar from './ar'
import en from './en'

const RTL = ['ar']
// During prerender there's no localStorage; default to Arabic (matches the static
// lang/dir in index.html), then the client reads the saved locale on load.
const saved = (!import.meta.env.SSR && localStorage.getItem('locale')) || 'ar'

export const i18n = createI18n({
  legacy: false,
  locale: saved,
  fallbackLocale: 'ar',
  messages: { ar, en },
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
