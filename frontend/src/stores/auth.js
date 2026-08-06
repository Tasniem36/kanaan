import { defineStore } from 'pinia'
import { api } from '../services/api'

// the `sub` (user id) baked into a JWT, so we can verify the cached user matches it
function tokenSub(token) {
  try {
    const b = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b + '='.repeat((4 - (b.length % 4)) % 4))).sub || null
  } catch { return null }
}

// Read the cached user ONLY if it belongs to the current token. This prevents a
// stale cached user (a previous/other account on this browser) from ever being
// shown while /auth/me is still resolving — the root cause of "wrong identity".
function cachedUser(token) {
  if (import.meta.env.SSR || !token) return null
  let u = null
  try { u = JSON.parse(localStorage.getItem('user') || 'null') } catch { u = null }
  const sub = tokenSub(token)
  if (u && u.id && sub && u.id !== sub) {
    localStorage.removeItem('user')
    return null
  }
  return u
}

export const useAuthStore = defineStore('auth', {
  state: () => {
    // No localStorage during prerender — start unauthenticated; the browser hydrates
    // the real session from localStorage on first client render.
    const token = import.meta.env.SSR ? null : localStorage.getItem('token') || null
    return {
      token,
      user: cachedUser(token), // cached so reloads/API hiccups keep you signed in — but only if it matches the token
      ready: false, // true once the initial fetchMe has resolved
    }
  },
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
