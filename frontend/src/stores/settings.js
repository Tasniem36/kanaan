import { defineStore } from 'pinia'
import { api } from '../services/api'

// Admin-editable delivery config: global (free threshold + default fee) + zones.
export const useSettingsStore = defineStore('settings', {
  state: () => ({ delivery: { free_threshold: 250, default_fee: 25, zones: [] } }),
  actions: {
    async fetchDelivery() {
      try {
        const { delivery } = await api('/settings/delivery')
        if (delivery) this.delivery = { zones: [], ...delivery }
      } catch { /* keep defaults */ }
    },
    async updateDelivery(patch) {
      const { delivery } = await api('/settings/delivery', { method: 'PATCH', body: patch })
      this.delivery = { zones: [], ...delivery }
      return delivery
    },
    async addZone(body) {
      await api('/settings/delivery/zones', { method: 'POST', body })
      await this.fetchDelivery()
    },
    async updateZone(id, body) {
      await api(`/settings/delivery/zones/${id}`, { method: 'PATCH', body })
      await this.fetchDelivery()
    },
    async deleteZone(id) {
      await api(`/settings/delivery/zones/${id}`, { method: 'DELETE' })
      await this.fetchDelivery()
    },
  },
})
