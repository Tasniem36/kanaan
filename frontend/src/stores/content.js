import { defineStore } from 'pinia'
import { api } from '../services/api'

// Admin-editable homepage content: the "why us" value cards and the section
// headings. Both fall back to the bundled i18n copy in the view.
export const useContentStore = defineStore('content', {
  state: () => ({ values: [], sections: {}, loaded: false, loading: false }),
  getters: {
    // section copy for the active language, with '' for anything the manager
    // hasn't filled in (the view then uses its i18n default)
    sectionCopy: (s) => (key, locale) => {
      const row = s.sections[key] || {}
      const pick = (f) => (row[`${f}_${locale === 'ar' ? 'ar' : 'en'}`] || '').trim()
      return { eyebrow: pick('eyebrow'), title: pick('title'), desc: pick('desc') }
    },
  },
  actions: {
    async fetch() {
      this.loading = true
      // one round-trip each, in parallel — a failure in either leaves that piece
      // empty and the view falls back to the bundled i18n defaults
      const [values, sections] = await Promise.all([
        api('/content/values').then((r) => r.values).catch(() => null),
        api('/content/sections').then((r) => r.sections).catch(() => null),
      ])
      if (values) this.values = values
      if (sections) this.sections = sections
      // mark the attempt done either way so the UI stops showing a loader
      this.loaded = true
      this.loading = false
    },
    async updateSection(key, copy) {
      const { section } = await api(`/content/sections/${key}`, { method: 'PATCH', body: copy })
      this.sections = { ...this.sections, [key]: section }
      return section
    },
    async updateValue(id, patch) {
      const { value } = await api(`/content/values/${id}`, { method: 'PATCH', body: patch })
      const i = this.values.findIndex((v) => v.id === id)
      if (i !== -1) this.values[i] = value
      return value
    },
    async deleteValue(id) {
      await api(`/content/values/${id}`, { method: 'DELETE' })
      this.values = this.values.filter((v) => v.id !== id)
    },
  },
})
