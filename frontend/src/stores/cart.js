import { defineStore } from 'pinia'
import { api } from '../services/api'
import { useAuthStore } from './auth'
import { pPrice } from '../utils/product'
import { track } from '../services/track'

const KEY = 'cart'

// restore the basket from a previous session; tolerate corrupt/old data
function loadItems() {
  if (import.meta.env.SSR) return {} // no localStorage during prerender
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null')
    return saved && typeof saved === 'object' ? saved : {}
  } catch {
    return {}
  }
}

// The basket ViewModel. Holds the full product object per line so it does not
// depend on the catalog being loaded to render the drawer. Persisted to
// localStorage so a refresh keeps whatever the customer added.
export const useCartStore = defineStore('cart', {
  state: () => ({
    items: loadItems(), // { [productId]: { product, qty } }
  }),
  getters: {
    count: (s) => Object.values(s.items).reduce((a, i) => a + i.qty, 0),
    list: (s) => Object.values(s.items).map((i) => ({ ...i.product, q: i.qty })),
    // pPrice, not i.price: a line on offer is totalled at the offer price. The server
    // re-reads both from the database at checkout, so this only has to agree with what
    // the shopper is being shown.
    total() {
      return this.list.reduce((sum, i) => sum + pPrice(i) * i.q, 0)
    },
    qty: (s) => (id) => s.items[id]?.qty || 0,
  },
  actions: {
    persist() {
      try {
        localStorage.setItem(KEY, JSON.stringify(this.items))
      } catch { /* storage full/blocked — cart just won't survive the refresh */ }
      this._pushToServer()
    },
    // debounced save to the server cart — only when signed in (so it syncs across devices)
    _pushToServer() {
      const auth = useAuthStore()
      if (!auth.isAuthenticated) return
      clearTimeout(this._t)
      this._t = setTimeout(() => {
        api('/cart', { method: 'PUT', body: { items: this.items } }).catch(() => {})
      }, 600)
    },
    // on login / app-boot: pull the server cart and merge (keep the larger qty per
    // product so nothing the customer added on either device is lost), then save back
    async loadFromServer() {
      const auth = useAuthStore()
      if (!auth.isAuthenticated) return
      try {
        const { items } = await api('/cart')
        if (items && typeof items === 'object') {
          const merged = { ...items }
          for (const [id, line] of Object.entries(this.items)) {
            if (!merged[id]) merged[id] = line
            else merged[id] = { product: merged[id].product || line.product, qty: Math.max(merged[id].qty, line.qty) }
          }
          this.items = merged
          this.persist()
        }
      } catch { /* offline — keep the local cart */ }
    },
    add(product) {
      if (this.items[product.id]) this.items[product.id].qty++
      else this.items[product.id] = { product, qty: 1 }
      this.persist()
      // Recorded here rather than at each button, so every route into the basket is
      // counted: the card, the product page, the related row, the saved list. The
      // server collapses repeats of the same product within a sitting.
      track('cart_add', { product_id: product.id, name: product.name, qty: this.items[product.id].qty })
    },
    dec(id) {
      const it = this.items[id]
      if (!it) return
      it.qty--
      if (it.qty <= 0) delete this.items[id]
      this.persist()
    },
    removeAll(id) {
      delete this.items[id]
      this.persist()
    },
    clear() {
      this.items = {}
      this.persist()
    },
  },
})
