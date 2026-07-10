import { createI18n } from 'vue-i18n'
import ar from './ar'
import en from './en'

const RTL = ['ar']
const saved = localStorage.getItem('locale') || 'ar'

export const i18n = createI18n({
  legacy: false,
  locale: saved,
  fallbackLocale: 'ar',
  messages: { ar, en },
})

// Reflect the active locale on <html lang/dir> so layout flips RTL ↔ LTR.
export function applyDir(locale = i18n.global.locale.value) {
  document.documentElement.lang = locale
  document.documentElement.dir = RTL.includes(locale) ? 'rtl' : 'ltr'
}

export function setLocale(locale) {
  i18n.global.locale.value = locale
  localStorage.setItem('locale', locale)
  applyDir(locale)
}

applyDir() // sync on load
