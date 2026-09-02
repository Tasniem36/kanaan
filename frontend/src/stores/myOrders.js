import { defineStore } from 'pinia'
import { api } from '../services/api'

const KEY = 'my_orders'
// One cap, not two: the list shows a live status on every row it renders, so keeping
// more than we're willing to fetch statuses for just leaves rows with a blank badge.
const MAX = 10

// A guest's own orders, remembered on the device that placed them.
//
// There is no account to hang them on — that's what makes them guest orders — but
// each one already carries its tracking token, which is the credential the status
// page runs on. Keeping the (id, token) pairs together is enough to give a guest one
// list of everything they've ordered, without asking them to sign in or to keep the
// confirmation to hand.
//
// What this is NOT: a way back in from another device, or after the browser's storage
// is cleared. For that there is the tracking link in the WhatsApp confirmation, and
// /orders/lookup with the order number plus a phone. Those are the durable routes;
// this is the convenient one.
function load() {
  if (import.meta.env.SSR) return []
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null')
    // tolerate anything: a half-written value, an older shape, a hand-edited key
    return Array.isArray(saved) ? saved.filter((o) => o && o.id && o.token) : []
  } catch {
    return []
  }
}

export const useMyOrdersStore = defineStore('myOrders', {
  state: () => ({
    items: load(),        // [{ id, token, ref, at }] — newest first
    statuses: {},         // id → { status, total, created_at } once fetched
    loading: false,
  }),
  getters: {
    count: (s) => s.items.length,
    // what the list renders: the remembered stub, filled in with the live status
    // when we have it
    list: (s) => s.items.map((o) => ({ ...o, ...(s.statuses[o.id] || {}) })),
  },
  actions: {
    persist() {
      try {
        localStorage.setItem(KEY, JSON.stringify(this.items))
      } catch { /* storage full or blocked — the list just won't outlive the tab */ }
    },
    // Called when a guest's order goes through. Idempotent: placing the same order
    // twice can't happen, but a re-render or a retry mustn't double the row.
    remember(order) {
      if (!order?.id || !order?.track_token) return
      const row = {
        id: String(order.id),
        token: String(order.track_token),
        ref: order.ref || null,
        at: order.created_at || new Date().toISOString(),
      }
      this.items = [row, ...this.items.filter((o) => o.id !== row.id)].slice(0, MAX)
      this.persist()
    },
    forget(id) {
      this.items = this.items.filter((o) => o.id !== id)
      delete this.statuses[id]
      this.persist()
    },
    clear() {
      this.items = []
      this.statuses = {}
      this.persist()
    },
    // Fetch where each remembered order has got to. One request each — the status
    // page's own endpoint, authorised by the token we stored — so it's capped, and a
    // 404 (an order deleted, or a token no longer valid) drops the row rather than
    // leaving something in the list that can't be opened.
    async fetchStatuses() {
      const batch = this.items
      if (!batch.length) return
      this.loading = true
      try {
        const results = await Promise.all(batch.map(async (o) => {
          try {
            const { order } = await api(`/orders/track/${o.id}?t=${encodeURIComponent(o.token)}`, { auth: true })
            // payment_method comes along because 'pending' reads differently on a
            // cash order ("being processed") than on an unpaid card one ("awaiting
            // payment") — see status.pendingCod in the translations
            return [o.id, { status: order.status, total: order.total, created_at: order.created_at,
                            number: order.number, payment_method: order.payment_method }]
          } catch (e) {
            return [o.id, e.status === 404 ? null : undefined]
          }
        }))
        const gone = []
        for (const [id, value] of results) {
          if (value === null) gone.push(id)
          else if (value !== undefined) this.statuses[id] = value
        }
        if (gone.length) {
          this.items = this.items.filter((o) => !gone.includes(o.id))
          for (const id of gone) delete this.statuses[id]
          this.persist()
        }
      } finally {
        this.loading = false
      }
    },
  },
})
