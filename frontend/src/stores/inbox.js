import { defineStore } from 'pinia'
import { api } from '../services/api'

// In-app notifications (bell) + customer<->shop support messages.
// The bell badge = unread notifications; new orders / messages / replies all
// create notifications, so that single count covers everything for both roles.
export const useInboxStore = defineStore('inbox', {
  state: () => ({
    notifications: [],
    unread: 0,
    messages: [],   // the signed-in customer's own thread
    threads: [],    // manager: list of customer threads
    openChatSignal: 0,  // bumped to ask the bell to open straight to the chat tab
    _timer: null,
  }),
  actions: {
    // ask the NotificationBell to open on the messages/chat tab (e.g. from "Contact us")
    requestChat() { this.openChatSignal++ },
    async fetchNotifications() {
      try {
        const { notifications, unread } = await api('/notifications')
        this.notifications = notifications
        this.unread = unread
      } catch { /* offline / not logged in */ }
    },
    async markRead() {
      if (!this.unread) return
      this.unread = 0
      this.notifications = this.notifications.map((n) => ({ ...n, read: true }))
      try { await api('/notifications/read', { method: 'POST' }) } catch { /* ignore */ }
    },
    // --- customer thread ---
    async fetchMessages() {
      try { const { messages } = await api('/messages'); this.messages = messages } catch { /* ignore */ }
    },
    async sendMessage(body, orderId = null) {
      const { message } = await api('/messages', { method: 'POST', body: { body, order_id: orderId } })
      this.messages.push(message)
      return message
    },
    // --- manager ---
    async fetchThreads() {
      try { const { threads } = await api('/messages/threads'); this.threads = threads } catch { /* ignore */ }
    },
    async fetchThread(uid) {
      return api(`/messages/thread/${uid}`)   // { messages, customer }
    },
    async reply(uid, body) {
      const { message } = await api(`/messages/thread/${uid}`, { method: 'POST', body: { body } })
      return message
    },
    // --- polling (badge stays fresh while the app is open) ---
    startPolling() {
      this.stopPolling()
      this.fetchNotifications()
      // poll fairly often so new notifications appear without a page refresh;
      // also refetch the moment the tab regains focus
      this._timer = setInterval(() => this.fetchNotifications(), 20000)
      this._onFocus = () => { if (!document.hidden) this.fetchNotifications() }
      document.addEventListener('visibilitychange', this._onFocus)
    },
    stopPolling() {
      if (this._timer) { clearInterval(this._timer); this._timer = null }
      if (this._onFocus) { document.removeEventListener('visibilitychange', this._onFocus); this._onFocus = null }
    },
  },
})
