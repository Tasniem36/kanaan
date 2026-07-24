import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useOrdersStore = defineStore('orders', {
  state: () => ({
    orders: [],
    loading: false,
  }),
  actions: {
    // items: [{ product_id, qty }]; delivery: {...}; paymentMethod: 'cod' | 'ziina'
    // returns { order, redirect_url? } — redirect_url is present for Ziina
    async place(delivery, items, paymentMethod = 'cod', code = null) {
      return api('/orders', { method: 'POST', body: { ...delivery, items, payment_method: paymentMethod, code }, auth: true })
    },
    async validateCode(code, subtotal) {
      return api('/discounts/validate', { method: 'POST', body: { code, subtotal } })
    },
    async confirmPayment(orderId) {
      return api(`/orders/${orderId}/confirm-payment`, { method: 'POST', auth: false })
    },
    async cancelPayment(orderId) {
      return api(`/orders/${orderId}/cancel-payment`, { method: 'POST', auth: false })
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
