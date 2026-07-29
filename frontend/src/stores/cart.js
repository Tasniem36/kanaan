import { defineStore } from 'pinia'

const KEY = 'cart'

// restore the basket from a previous session; tolerate corrupt/old data
function loadItems() {
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
    total() {
      return this.list.reduce((sum, i) => sum + i.price * i.q, 0)
    },
    qty: (s) => (id) => s.items[id]?.qty || 0,
  },
  actions: {
    persist() {
      try {
        localStorage.setItem(KEY, JSON.stringify(this.items))
      } catch { /* storage full/blocked — cart just won't survive the refresh */ }
    },
    add(product) {
      if (this.items[product.id]) this.items[product.id].qty++
      else this.items[product.id] = { product, qty: 1 }
      this.persist()
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
