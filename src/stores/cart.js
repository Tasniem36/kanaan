import { defineStore } from 'pinia'

// The basket ViewModel. Holds the full product object per line so it does not
// depend on the catalog being loaded to render the drawer.
export const useCartStore = defineStore('cart', {
  state: () => ({
    items: {}, // { [productId]: { product, qty } }
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
    add(product) {
      if (this.items[product.id]) this.items[product.id].qty++
      else this.items[product.id] = { product, qty: 1 }
    },
    dec(id) {
      const it = this.items[id]
      if (!it) return
      it.qty--
      if (it.qty <= 0) delete this.items[id]
    },
    removeAll(id) {
      delete this.items[id]
    },
    clear() {
      this.items = {}
    },
  },
})
