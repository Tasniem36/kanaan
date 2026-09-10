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
    // `token` is the order's tracking token: how a guest returning from Ziina
    // proves the order is theirs, since they have no session. Signed-in customers
    // pass '' and are authorised by their JWT as before.
    async confirmPayment(orderId, token = '') {
      return api(`/orders/${orderId}/confirm-payment?t=${encodeURIComponent(token)}`, { method: 'POST' })
    },
    async cancelPayment(orderId, token = '') {
      return api(`/orders/${orderId}/cancel-payment?t=${encodeURIComponent(token)}`, { method: 'POST' })
    },
    // `mine` asks for the caller's own orders even when the caller is a manager.
    // حسابي and the manager area share this store, and the endpoint widens to the
    // whole shop for a manager — which is right for the till and very wrong for
    // طلباتي, where it filed every customer's order under the manager's own name.
    async fetch({ mine = false } = {}) {
      this.loading = true
      try {
        const { orders } = await api(mine ? '/orders?mine=1' : '/orders')
        this.orders = orders
      } finally {
        this.loading = false
      }
    },
    async setStatus(id, status) {
      const { order } = await api(`/orders/${id}/status`, { method: 'PATCH', body: { status } })
      const i = this.orders.findIndex((o) => o.id === id)
      if (i !== -1) {
        // extend the tracking timeline too, so the open order stays truthful
        // without a full refetch
        const prev = this.orders[i]
        const events = [...(prev.events || []), { order_id: id, status: order.status, created_at: new Date().toISOString() }]
        this.orders[i] = { ...prev, status: order.status, events }
      }
      return order
    },
    // soft-delete on the server (kept in the DB, just hidden); drop it from the list
    async hide(id) {
      await api(`/orders/${id}`, { method: 'DELETE' })
      this.orders = this.orders.filter((o) => o.id !== id)
    },
  },
})
