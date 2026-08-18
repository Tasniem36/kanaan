import { defineStore } from 'pinia'
import { api } from '../services/api'

// Admin-editable shop config: delivery (threshold, fees, zones) and the checkout
// policy (whether someone may order without an account).
export const useSettingsStore = defineStore('settings', {
  state: () => ({
    delivery: { free_threshold: 250, default_fee: 25, zones: [] },
    // mirrors the server default: ordering needs an account until the manager
    // allows guests, so a failed fetch can't accidentally open checkout up
    checkout: { guest_allowed: false },
    checkoutLoaded: false,
  }),
  actions: {
    async fetchCheckout() {
      try {
        const { checkout } = await api('/settings/checkout')
        if (checkout) this.checkout = checkout
      } catch {
        /* keep the closed default */
      } finally {
        this.checkoutLoaded = true
      }
    },
    async updateCheckout(patch) {
      const { checkout } = await api('/settings/checkout', { method: 'PATCH', body: patch })
      this.checkout = checkout
      return checkout
    },
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
