import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    user: JSON.parse(localStorage.getItem('user') || 'null'), // cached so reloads/API hiccups keep you signed in
    ready: false, // true once the initial fetchMe has resolved
  }),
  getters: {
    isAuthenticated: (s) => !!s.token,
    isManager: (s) => s.user?.role === 'manager',
  },
  actions: {
    setSession(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    async register(payload) {
      const { token, user } = await api('/auth/register', { method: 'POST', body: payload, auth: false })
      this.setSession(token, user)
    },
    async login(email, password) {
      const { token, user } = await api('/auth/login', { method: 'POST', body: { email, password }, auth: false })
      this.setSession(token, user)
    },
    async fetchMe() {
      if (!this.token) {
        this.ready = true
        return
      }
      try {
        const { user } = await api('/auth/me')
        this.user = user
        localStorage.setItem('user', JSON.stringify(user))
      } catch (e) {
        // Only a truly invalid/expired token logs you out. Transient errors
        // (API down, network) keep the cached session so you stay signed in.
        if (e.status === 401) this.logout()
      } finally {
        this.ready = true
      }
    },
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
