import { defineStore } from 'pinia'
import { api } from '../services/api'
import { reportError } from '../services/report'

// Hiding the band protects the customer from a threshold the shop may not honour,
// but it also means the offer can stop appearing and nobody would ever notice. So
// the shop is told, in the السجلّات error list, what actually broke for a shopper.
//
// Once a visit. api() already reports a 5xx by itself, and one customer on a bad
// connection must not fill the log with the same line — the manager only needs
// telling once to go and look.
let _deliveryOffReported = false

function _reportDeliveryOff(why) {
  if (_deliveryOffReported) return
  _deliveryOffReported = true
  reportError(
    'The free-delivery offer is not being shown to customers',
    `${why}. The band can only quote a threshold once /settings/delivery has loaded, `
    + 'so until it does it stays hidden rather than advertise a number the shop may '
    + 'have changed. Check that the API is reachable and that GET /api/settings/delivery '
    + 'answers with a "delivery" object.',
  )
}

// Admin-editable shop config: delivery (threshold, fees, zones) and the checkout
// policy (whether someone may order without an account).
export const useSettingsStore = defineStore('settings', {
  state: () => ({
    delivery: { free_threshold: 250, default_fee: 25, zones: [] },
    // mirrors the server default: ordering needs an account until the manager
    // allows guests, so a failed fetch can't accidentally open checkout up
    checkout: { guest_allowed: false },
    checkoutLoaded: false,
    // free_threshold above is a guess at the server's default. Until the real one
    // lands, anything quoting it to a customer is quoting a number the shop may not
    // actually offer — so the delivery nudge waits for this.
    deliveryLoaded: false,
  }),
  actions: {
    async fetchCheckout() {
      try {
        const { checkout } = await api('/settings/checkout')
        if (checkout) this.checkout = checkout
      } catch {
        /* keep the closed default */
      } finally {
        this.checkoutLoaded = true
      }
    },
    async updateCheckout(patch) {
      const { checkout } = await api('/settings/checkout', { method: 'PATCH', body: patch })
      this.checkout = checkout
      return checkout
    },
    async fetchDelivery() {
      // Several places want this on the same page load (the header nudge, the cart
      // drawer, the home page). One request between them.
      if (this._deliveryReq) return this._deliveryReq
      this._deliveryReq = (async () => {
        try {
          const { delivery } = await api('/settings/delivery')
          if (delivery) {
            this.delivery = { zones: [], ...delivery }
            // Marked loaded only here. free_threshold above is the store's guess at
            // the server default until this lands, and setting the flag whatever
            // happened would have the delivery nudge quote that guess — a shop that
            // has moved its threshold would advertise the old number and then charge
            // for delivery at checkout, where the server uses the real one. Silent is
            // recoverable; wrong out loud is not.
            this.deliveryLoaded = true
            return
          }
          // A 200 with nothing in it is the API answering in a shape this store does
          // not know — a real fault, and the one api() cannot see for itself.
          _reportDeliveryOff('the server answered without a delivery config')
        } catch (e) {
          _reportDeliveryOff(`the request failed (${e?.status || 'no response'})`)
        }
        // Anything but success: left unloaded so nothing quotes a number, and the
        // shared request is dropped so the next page that wants it asks again. One
        // blip should not switch the nudge off for the rest of the visit.
        this._deliveryReq = null
      })()
      return this._deliveryReq
    },
    async updateDelivery(patch) {
      const { delivery } = await api('/settings/delivery', { method: 'PATCH', body: patch })
      this.delivery = { zones: [], ...delivery }
      return delivery
    },
    async addZone(body) {
      await api('/settings/delivery/zones', { method: 'POST', body })
      await this.fetchDelivery()
    },
    async updateZone(id, body) {
      await api(`/settings/delivery/zones/${id}`, { method: 'PATCH', body })
      await this.fetchDelivery()
    },
    async deleteZone(id) {
      await api(`/settings/delivery/zones/${id}`, { method: 'DELETE' })
      await this.fetchDelivery()
    },
  },
})
