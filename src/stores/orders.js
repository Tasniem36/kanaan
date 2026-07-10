import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useOrdersStore = defineStore('orders', {
  state: () => ({
    orders: [],
    loading: false,
  }),
  actions: {
    // items: [{ product_id, qty }]; delivery: { customer_name, phone, city, street, house, notes }
    async place(delivery, items) {
      const { order } = await api('/orders', { method: 'POST', body: { ...delivery, items }, auth: true })
      return order
    },
    async fetch() {
      this.loading = true
      try {
        const { orders } = await api('/orders')
        this.orders = orders
      } finally {
        this.loading = false
      }
    },
    async setStatus(id, status) {
      const { order } = await api(`/orders/${id}/status`, { method: 'PATCH', body: { status } })
      const i = this.orders.findIndex((o) => o.id === id)
      if (i !== -1) this.orders[i] = { ...this.orders[i], status: order.status }
      return order
    },
  },
})
