import { defineStore } from 'pinia'
import { api } from '../services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    // No localStorage during prerender — start unauthenticated; the browser hydrates
    // the real session from localStorage on first client render.
    token: import.meta.env.SSR ? null : localStorage.getItem('token') || null,
    user: import.meta.env.SSR ? null : JSON.parse(localStorage.getItem('user') || 'null'), // cached so reloads/API hiccups keep you signed in
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
    // step 1 — validate details + send codes for whichever channels are configured.
    // If no channel needs verifying, the account is created straight away.
    async registerStart(payload) {
      const res = await api('/auth/register', { method: 'POST', body: payload, auth: false })
      if (res.verified) this.setSession(res.token, res.user)
      return res
    },
    // step 2 — verify both codes; logs in only when { verified: true }
    async registerVerify(verificationId, emailCode, phoneCode) {
      const res = await api('/auth/register/verify', {
        method: 'POST', auth: false,
        body: { verification_id: verificationId, email_code: emailCode, phone_code: phoneCode },
      })
      if (res.verified) this.setSession(res.token, res.user)
      return res
    },
    async registerResend(verificationId) {
      return api('/auth/register/resend', { method: 'POST', body: { verification_id: verificationId }, auth: false })
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
