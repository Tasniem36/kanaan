import { defineStore } from 'pinia'
import { api } from '../services/api'
import { useAuthStore } from './auth'

// Saved products. The set of ids is loaded once per session so every product card
// can fill in its heart without a request of its own; the full product rows are
// only fetched when the customer opens the wishlist page.
export const useWishlistStore = defineStore('wishlist', {
  state: () => ({
    ids: new Set(),
    products: [],
    loading: false,
    loaded: false,
  }),
  getters: {
    count: (s) => s.ids.size,
    has: (s) => (id) => s.ids.has(id),
  },
  actions: {
    // called on login/boot alongside the cart sync
    async loadIds() {
      const auth = useAuthStore()
      if (!auth.isAuthenticated) return
      try {
        const { ids } = await api('/wishlist/ids')
        this.ids = new Set(ids || [])
      } catch { /* offline — hearts just render empty */ }
    },
    async fetch() {
      this.loading = true
      try {
        const { products } = await api('/wishlist')
        this.products = products
        this.ids = new Set(products.map((p) => p.id))
        this.loaded = true
      } finally {
        this.loading = false
      }
    },
    // Flips the heart immediately and reverts if the server rejects it — waiting
    // on a round-trip to fill in a heart feels broken.
    async toggle(product) {
      const id = product.id
      const wasSaved = this.ids.has(id)
      if (wasSaved) {
        this.ids.delete(id)
        this.products = this.products.filter((p) => p.id !== id)
      } else {
        this.ids.add(id)
        if (this.loaded) this.products = [product, ...this.products]
      }
      try {
        await api(`/wishlist/${id}`, { method: wasSaved ? 'DELETE' : 'PUT' })
      } catch (e) {
        if (wasSaved) this.ids.add(id)
        else this.ids.delete(id)
        this.loaded = false // list may be out of sync now; refetch on next open
        throw e
      }
      return !wasSaved
    },
    clear() {
      this.ids = new Set()
      this.products = []
      this.loaded = false
    },
  },
})
