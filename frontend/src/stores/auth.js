import { defineStore } from 'pinia'
import { api } from '../services/api'
import { useCartStore } from './cart'
import { useWishlistStore } from './wishlist'
import { useInboxStore } from './inbox'
import { useAddressesStore } from './addresses'
import { useOrdersStore } from './orders'

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
    // forgotten password, step 1 — ask for a code. Always resolves the same way
    // whether or not the address has an account, so the UI can't leak that either.
    async forgotPassword(email) {
      return api('/auth/password/forgot', { method: 'POST', body: { email }, auth: false })
    },
    // step 2 — spend the code on a new password; a success signs them straight in
    async resetPassword(email, code, password) {
      const { token, user } = await api('/auth/password/reset', {
        method: 'POST', auth: false, body: { email, code, password },
      })
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
    // Ends the session AND drops everything on this device that belonged to it, so a
    // signed-out browser holds nothing of the last customer for whoever picks it up
    // next. It has to happen here rather than on the navigation that follows a
    // sign-out: signing out from the page you're already on ('/' from the menu) is a
    // duplicate navigation, which vue-router resolves without ever running a guard —
    // and the 401 path above signs you out with no navigation at all.
    //
    // The token is cleared FIRST: cart and wishlist only write back while signed in,
    // so emptying them after this cannot be pushed over the server copies, which are
    // kept and come back in full on the next sign-in.
    //
    // The rest is in-memory only, so a reload would take care of it — but a sign-out
    // followed by a sign-in in the same tab never reloads, and the next customer
    // would be looking at what's left. Not one of these is safe to leave on the
    // grounds that nothing renders it today: the bell already does (it remounts and
    // switches to the messages tab before the fetch it fires can answer), and the
    // other two are only out of sight because every template that reads them
    // remembers to ask whether anyone is signed in. What isn't there can't leak.
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      useCartStore().clear()
      useWishlistStore().clear()
      // before the reset, so the poll interval and its listener actually go: they're
      // held in state, and $reset would only overwrite the handles. This is also what
      // stops a 401 mid-poll from coming straight back round every 20 seconds.
      const inbox = useInboxStore()
      inbox.stopPolling()
      inbox.$reset()          // notifications, unread badge, support thread
      useAddressesStore().$reset()  // name, phone, street
      useOrdersStore().$reset()     // manager: every customer's order, with their details
    },
  },
})
