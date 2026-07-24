import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useAddressesStore = defineStore('addresses', {
  state: () => ({
    addresses: [],
    loading: false,
  }),
  getters: {
    default: (s) => s.addresses.find((a) => a.is_default) || s.addresses[0] || null,
  },
  actions: {
    async fetch() {
      this.loading = true
      try {
        const { addresses } = await api('/addresses')
        this.addresses = addresses
      } finally {
        this.loading = false
      }
    },
    async add(payload) {
      const { address } = await api('/addresses', { method: 'POST', body: payload })
      await this.fetch() // re-sync (default flag may have moved)
      return address
    },
    async remove(id) {
      await api(`/addresses/${id}`, { method: 'DELETE' })
      this.addresses = this.addresses.filter((a) => a.id !== id)
    },
    async makeDefault(id) {
      await api(`/addresses/${id}`, { method: 'PATCH', body: { is_default: true } })
      await this.fetch()
    },
  },
})
