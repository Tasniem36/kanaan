import { defineStore } from 'pinia'
import { api } from '../services/api'

// decode a JWT payload (client-side, unverified — only for reading role/sub for UI)
function decodeToken(token) {
  try {
    const b = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b + '='.repeat((4 - (b.length % 4)) % 4)))
  } catch { return null }
}

export const useAuthStore = defineStore('auth', {
  state: () => {
    const ssr = import.meta.env.SSR
    // ONLY the JWT is persisted. The user profile is never stored in localStorage
    // (it's fetched from /auth/me into memory), so a stale/other identity can't leak.
    const token = ssr ? null : localStorage.getItem('token') || null
    if (!ssr) localStorage.removeItem('user') // purge any legacy cached user
    return { token, user: null, ready: false }
  },
  getters: {
    isAuthenticated: (s) => !!s.token,
    // role is read from the token immediately (so the admin link shows on reload),
    // and stays in sync with the fetched user
    isManager: (s) => (s.user?.role || decodeToken(s.token)?.role) === 'manager',
  },
  actions: {
    setSession(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token) // only the JWT
    },
    // step 1 — validate details + send codes for whichever channels are configured.
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
    // update the signed-in customer's own name/phone (email is not editable)
    async updateProfile(patch) {
      const { user } = await api('/auth/me', { method: 'PATCH', body: patch })
      this.user = user
      return user
    },
    async fetchMe() {
      if (!this.token) { this.ready = true; return }
      try {
        const { user } = await api('/auth/me')
        this.user = user // in memory only
      } catch (e) {
        // only a truly invalid/expired token logs you out; transient errors keep the token
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
