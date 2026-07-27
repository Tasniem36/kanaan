import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    products: [],
    loading: false,
    error: '',
  }),
  getters: {
    // storefront sections: active products only (managers get all products from
    // the API, so filter here too or hidden ones would still show on the store)
    pantry: (s) => s.products.filter((p) => p.category === 'pantry' && p.is_active !== false),
    pottery: (s) => s.products.filter((p) => p.category === 'pottery' && p.is_active !== false),
    // sorted low→high for the manager inventory view (includes hidden products)
    byStock: (s) => [...s.products].sort((a, b) => a.stock - b.stock),
  },
  actions: {
    async fetch() {
      this.loading = true
      this.error = ''
      try {
        const { products } = await api('/products')
        this.products = products
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    // full-quality single product (with the gallery) for the detail page
    async fetchOne(id) {
      const { product } = await api(`/products/${id}`)
      const i = this.products.findIndex((p) => p.id === id)
      if (i !== -1) this.products[i] = product
      else this.products.push(product)
      return product
    },
    async create(payload) {
      const { product } = await api('/products', { method: 'POST', body: payload })
      this.products.push(product)
      return product
    },
    async update(id, patch) {
      const { product } = await api(`/products/${id}`, { method: 'PATCH', body: patch })
      const i = this.products.findIndex((p) => p.id === id)
      if (i !== -1) this.products[i] = product
      return product
    },
    async restock(id, qty) {
      const { product } = await api(`/products/${id}/restock`, { method: 'POST', body: { qty } })
      const i = this.products.findIndex((p) => p.id === id)
      if (i !== -1) this.products[i] = product
      return product
    },
    async remove(id) {
      await api(`/products/${id}`, { method: 'DELETE' })
      // refetch so soft-deleted (still-referenced) products drop out of the list
      await this.fetch()
    },
  },
})
