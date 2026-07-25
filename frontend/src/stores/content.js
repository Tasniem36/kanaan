import { defineStore } from 'pinia'
import { api } from '../services/api'

// Editable "why us" value cards, served from the backend (fall back to i18n in the view).
export const useContentStore = defineStore('content', {
  state: () => ({ values: [], loaded: false }),
  actions: {
    async fetch() {
      try {
        const { values } = await api('/content/values')
        this.values = values
        this.loaded = true
      } catch {
        /* leave values empty — the view falls back to the bundled i18n defaults */
      }
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
