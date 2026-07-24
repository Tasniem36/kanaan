import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    products: [],
    loading: false,
    error: '',
  }),
  getters: {
    pantry: (s) => s.products.filter((p) => p.category === 'pantry'),
    pottery: (s) => s.products.filter((p) => p.category === 'pottery'),
    // sorted low→high for the manager inventory view
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
