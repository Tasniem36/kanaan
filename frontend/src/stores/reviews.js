import { defineStore } from 'pinia'
import { api } from '../services/api'
import { useAuthStore } from './auth'
import { useContentStore } from './content'

const PAGE = 3      // the storefront shows the best three, then "show all"
const BATCH_MAX = 50 // the endpoint's per-request cap

// General shop reviews (not per-product). The storefront only ever sees approved
// ones; `mine` is the signed-in customer's own, which may still be pending.
export const useReviewsStore = defineStore('reviews', {
  state: () => ({
    list: [],          // approved reviews, newest first
    total: 0,          // how many approved ones exist in all
    average: null,     // average rating across all approved ones
    loading: false,
    loaded: false,
    mine: [],          // every review the caller wrote, any status
    mineLoaded: false,
    queue: [],         // manager: the moderation list
    queueLoading: false,
    pending: 0,        // manager: pending count, for the tab badge
  }),
  getters: {
    hasMore: (s) => s.list.length < s.total,
    // ids of the caller's own reviews — the card shows a pencil for these
    mineIds: (s) => new Set(s.mine.map((r) => r.id)),
    // What the section renders: the approved reviews everyone sees, plus the
    // caller's own not-yet-approved ones, which nobody else can see. Without them
    // a customer would have nowhere to click to edit what they just wrote.
    cards: (s) => {
      const shown = new Set(s.list.map((r) => r.id))
      const ownUnpublished = s.mine.filter((r) => !shown.has(r.id) && r.status !== 'approved')
      return [...ownUnpublished, ...s.list]
    },
    // Two gates on the homepage section:
    //  1. the manager's switch in /manager/content wins outright — off means off;
    //  2. otherwise it stays hidden until something is approved, because an empty
    //     testimonials block above the shop looks worse than no block at all.
    // Signed-in customers are exempt from (2): they're the only ones who can write
    // a review, so hiding it from them would leave the very first one unwritable.
    visible() {
      if (useContentStore().sectionHidden('reviews')) return false
      return this.total > 0 || useAuthStore().isAuthenticated
    },
  },
  actions: {
    // first page (replaces what's there) — safe to call on every section mount
    async fetch() {
      this.loading = true
      try {
        const { reviews, total, average } = await api(`/reviews?limit=${PAGE}`, { auth: false })
        this.list = reviews || []
        this.total = total || 0
        this.average = average
        this.loaded = true
      } catch {
        /* offline — the section falls back to its empty state */
      } finally {
        this.loading = false
      }
    },
    // "show all": pull everything that's left in one request. Past the endpoint's
    // cap the button simply stays for another click, rather than firing 20 requests.
    async loadMore() {
      if (this.loading || !this.hasMore) return
      this.loading = true
      try {
        const want = Math.min(Math.max(this.total - this.list.length, 1), BATCH_MAX)
        const { reviews, total, average } = await api(
          `/reviews?limit=${want}&offset=${this.list.length}`, { auth: false })
        // de-duplicate: a review approved between two pages would otherwise shift
        // rows down and repeat one across the boundary
        const seen = new Set(this.list.map((r) => r.id))
        this.list = [...this.list, ...(reviews || []).filter((r) => !seen.has(r.id))]
        this.total = total || 0
        this.average = average
      } finally {
        this.loading = false
      }
    },
    async fetchMine() {
      const auth = useAuthStore()
      if (!auth.isAuthenticated) { this.mine = []; this.mineLoaded = true; return }
      try {
        const { reviews } = await api('/reviews/mine')
        this.mine = reviews || []
      } catch {
        /* leave it unknown — the form still opens, submitting is what matters */
      } finally {
        this.mineLoaded = true
      }
    },
    // Add a review. It starts out pending, so it shows only to its author until a
    // manager approves it. `image` is an optional uploaded data-URL.
    async submit({ rating, body, city, image }) {
      const { review } = await api('/reviews', { method: 'POST', body: { rating, body, city, image } })
      this.mine = [review, ...this.mine]
      return review
    },
    // Edit one of the caller's own. Editing re-queues it, so a published review
    // leaves the public list until it's approved again.
    async update(id, { rating, body, city, image }) {
      const { review } = await api(`/reviews/${id}`, { method: 'PUT', body: { rating, body, city, image } })
      this.mine = this.mine.map((r) => (r.id === id ? review : r))
      if (this.list.some((r) => r.id === id)) {
        this.list = this.list.filter((r) => r.id !== id)
        await this.refreshSummary()
      }
      return review
    },
    async remove(id) {
      const queued = this.queue.find((r) => r.id === id)
      await api(`/reviews/${id}`, { method: 'DELETE' })
      this.mine = this.mine.filter((r) => r.id !== id)
      if (this.list.some((r) => r.id === id)) {
        this.list = this.list.filter((r) => r.id !== id)
        await this.refreshSummary()
      } else if (queued?.status === 'approved') {
        this.loaded = false // a manager deleted a published one — refetch on next mount
      }
      this.queue = this.queue.filter((r) => r.id !== id)
      if (queued?.status === 'pending') this.pending = Math.max(0, this.pending - 1)
    },
    // A review leaving the public list makes both the count and the average stale.
    // The average can't be derived locally — the server rounds it to one decimal, so
    // backing the sum out of it drifts — and one row re-reads both authoritatively.
    async refreshSummary() {
      try {
        const { total, average } = await api('/reviews?limit=1', { auth: false })
        this.total = total || 0
        this.average = average
      } catch {
        this.total = Math.max(0, this.total - 1) // offline: at least keep the count honest
      }
    },
    clearMine() {
      this.mine = []
      this.mineLoaded = false
    },

    // --- manager ---
    async fetchQueue(status = '') {
      this.queueLoading = true
      try {
        const { reviews } = await api(`/reviews/all${status ? `?status=${status}` : ''}`)
        this.queue = reviews || []
        if (!status) this.pending = this.queue.filter((r) => r.status === 'pending').length
      } finally {
        this.queueLoading = false
      }
    },
    async fetchPendingCount() {
      const { pending } = await api('/reviews/pending-count')
      this.pending = pending || 0
      return this.pending
    },
    async setStatus(id, status) {
      const row = this.queue.find((r) => r.id === id)
      const was = row?.status
      const { review } = await api(`/reviews/${id}`, { method: 'PATCH', body: { status } })
      if (row) row.status = review.status
      // only a move in or out of 'pending' changes the badge
      if (was === 'pending' && review.status !== 'pending') this.pending = Math.max(0, this.pending - 1)
      else if (was && was !== 'pending' && review.status === 'pending') this.pending += 1
      // the storefront list is now stale either way — refetch it on next mount
      this.loaded = false
      return review
    },
  },
})
