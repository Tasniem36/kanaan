import { defineStore } from 'pinia'
import { api } from '../services/api'

// Admin-editable delivery config (fees + free-shipping threshold).
export const useSettingsStore = defineStore('settings', {
  state: () => ({ delivery: { fee_high: 30, fee_low: 25, free_threshold: 250 } }),
  actions: {
    async fetchDelivery() {
      try {
        const { delivery } = await api('/settings/delivery')
        if (delivery) this.delivery = delivery
      } catch { /* keep defaults */ }
    },
    async updateDelivery(patch) {
      const { delivery } = await api('/settings/delivery', { method: 'PATCH', body: patch })
      this.delivery = delivery
      return delivery
    },
  },
})
