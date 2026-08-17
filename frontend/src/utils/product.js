// Localised product text.
//
// Products store Arabic in the base columns (name, description, unit, tag) and
// English in the *_en ones. English is only used when it's actually filled in —
// a product the manager hasn't translated yet still reads correctly in Arabic
// rather than showing a blank name. Mirrors how content_values is rendered on
// the home page.
import { i18n } from '../i18n'

function pick(ar, en) {
  if (i18n.global.locale.value !== 'ar') {
    const t = typeof en === 'string' ? en.trim() : ''
    if (t) return t
  }
  return ar || ''
}

export const pName = (p) => (p ? pick(p.name, p.name_en) : '')
export const pDesc = (p) => (p ? pick(p.description, p.description_en) : '')
export const pUnit = (p) => (p ? pick(p.unit, p.unit_en) : '')
export const pTag = (p) => (p ? pick(p.tag, p.tag_en) : '')
