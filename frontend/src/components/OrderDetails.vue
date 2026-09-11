<template>
  <div class="od" :class="{ compact }">
    <OrderTimeline :status="order.status" :events="order.events || []" />

    <div v-show="open" class="od-part">
      <ul class="items">
        <li v-for="(it, i) in order.items || []" :key="i">
          <span class="nm">{{ it.name }}</span>
          <span class="a-muted qt">×{{ it.qty }}</span>
          <span class="pr">{{ fmt(it.price * it.qty) }} <span class="dh" role="img" aria-label="درهم"></span></span>
        </li>
      </ul>

      <div class="totals">
        <div v-if="Number(order.discount_amount) > 0" class="row">
          <span class="a-muted">{{ t('checkout.discountLine') }}</span>
          <span style="color:var(--red)">− {{ fmt(order.discount_amount) }} <span class="dh" role="img" aria-label="درهم"></span></span>
        </div>
        <div class="row">
          <span class="a-muted">{{ t('checkout.deliveryFee') }}</span>
          <span v-if="Number(order.delivery_fee) > 0">{{ fmt(order.delivery_fee) }} <span class="dh" role="img" aria-label="درهم"></span></span>
          <span v-else style="color:var(--green)">{{ t('checkout.freeDelivery') }}</span>
        </div>
        <div class="row total">
          <span>{{ t('checkout.total') }}</span>
          <span>{{ fmt(order.total) }} <span class="dh" role="img" aria-label="درهم"></span></span>
        </div>
        <!-- What actually happened to the money. Reading this off payment_method
             alone told somebody looking at an order they had never paid for that it
             was "الدفع الإلكتروني", with nothing to say it was still owed — the same
             mistake the confirmation e-mail used to make. -->
        <div class="row">
          <span class="a-muted">{{ t('checkout.payMethod') }}</span>
          <span :class="{ owed: awaiting, settled: order.payment_status === 'paid' }">
            {{ t(payKey) }}
          </span>
        </div>
      </div>
    </div>

    <!-- Never collapsed, on either page: an order that was released, or one still
         waiting to be paid for, is the whole reason its customer opened this. -->
    <section v-if="released" class="released" :aria-labelledby="'rel-h-' + order.id">
      <h2 :id="'rel-h-' + order.id">{{ t('track.releasedTitle') }}</h2>
      <p class="a-muted">{{ t('track.releasedMsg') }}</p>
      <!-- Said separately and plainly: the first thing somebody thinks on
           reading "cancelled" is whether they have been charged for it. -->
      <p class="a-muted">{{ t('track.releasedReassure') }}</p>
      <RouterLink to="/" class="btn btn-green">{{ t('track.orderAgain') }}</RouterLink>
    </section>

    <!-- An abandoned card checkout leaves a real order that nobody has paid for.
         Their way back in used to be building the whole basket again. -->
    <section v-if="awaiting" class="paynow" :aria-labelledby="'paynow-h-' + order.id">
      <h2 :id="'paynow-h-' + order.id">{{ t('track.awaitingTitle') }}</h2>
      <p class="a-muted">{{ t('track.awaitingMsg') }}</p>
      <!-- The amount stands on its own rather than inside the sentence: it is
           the one thing they need to recognise before choosing, and the same
           figure as the total above. -->
      <p class="paynow-amount">
        {{ fmt(order.total) }} <span class="dh" role="img" aria-label="درهم"></span>
      </p>
      <p v-if="payErr" class="err">{{ payErr }}</p>
      <div class="paynow-acts">
        <button class="btn btn-green" :disabled="!!paying" @click="choosePayment('ziina')">
          {{ paying === 'ziina' ? t('common.loading') : t('track.payNow') }}
        </button>
        <button class="btn btn-ghost" :disabled="!!paying" @click="choosePayment('cod')">
          {{ paying === 'cod' ? t('common.loading') : t('track.payOnDelivery') }}
        </button>
      </div>
    </section>

    <div v-show="open" class="od-part">
      <div v-if="order.city" class="deliv">
        <h2>{{ t('track.deliverTo') }}</h2>
        <p>{{ order.customer_name }}<span v-if="order.phone_hint" class="a-muted" dir="ltr"> · {{ order.phone_hint }}</span></p>
        <p class="a-muted">{{ t('account.addrLine', { city: order.city, street: order.street, house: order.house }) }}</p>
        <p v-if="order.notes" class="a-muted">{{ order.notes }}</p>
      </div>

      <p class="a-muted help">{{ t('track.wrongDetails') }}</p>
      <a class="btn btn-green wa" :href="whatsappLink(waText)" target="_blank" rel="noopener">{{ t('track.whatsapp') }}</a>
    </div>

    <!-- طلباتي lists ten of these at a time, and an order somebody is only scanning
         past doesn't need its lines, its address and its receipt open. Same content
         either way — one tap apart on the list, already open on the order's own page. -->
    <button v-if="compact" type="button" class="od-toggle" :aria-expanded="String(open)" @click="open = !open">
      {{ open ? t('track.hideDetails') : t('track.showDetails') }}
    </button>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import OrderTimeline from './OrderTimeline.vue'
import { api } from '../services/api'
import { whatsappLink } from '../utils/contact'
import { useCartStore } from '../stores/cart'
import { useConfirmStore } from '../stores/confirm'
import { takeOutOfBasket } from '../services/awaitingPayment'
import { isAwaitingPayment, isReleasedUnpaid, money, orderNumber, payLabelKey } from '../utils/order'

// One order, shown to the customer it belongs to.
//
// Both the places that do this — the public tracking page and طلباتي — render this,
// so a guest and a signed-in customer are told the same things about the same order
// in the same words. They used to be two screens that had drifted apart: different
// order numbers, different wording for one payment state, unformatted totals, and no
// explanation at all for a signed-in customer whose order the sweep had released.
const props = defineProps({
  order: { type: Object, required: true },
  // The tracking token, for a guest whose credential is the link they followed. A
  // signed-in customer opening their own order needs none — the session is enough.
  token: { type: String, default: '' },
  // In a list: the detail starts folded away. On an order's own page it is the page.
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['changed'])

const { t, locale } = useI18n()
const cart = useCartStore()
const confirm = useConfirmStore()

const open = ref(!props.compact)
const paying = ref('')
const payErr = ref('')

const fmt = (n) => money(n, locale.value)
const awaiting = computed(() => isAwaitingPayment(props.order))
const released = computed(() => isReleasedUnpaid(props.order))
const payKey = computed(() => payLabelKey(props.order))
// whatsappLink encodes it, so this is the plain sentence
const waText = computed(() => t('track.whatsappText', { id: orderNumber(props.order) }))

// Card sends them back to the payment page they walked away from; cash turns this
// into an ordinary cash-on-delivery order, which is also what takes it out of the
// sweep that would otherwise cancel it. Either way the page reloads and says what
// the order now is, rather than assuming the answer.
async function choosePayment(method) {
  // Cash commits: the order goes to the shop to prepare, and these buttons go away
  // because there is no longer a payment waiting to be finished. Card does not — a
  // payment page nobody completes changes nothing — so only this one asks.
  // (Switching a cash order back to card is deliberately not offered yet; the
  // endpoint would take it, but an unpaid card order is on the sweep's clock and a
  // customer who tapped it out of curiosity would lose an order the shop had.)
  if (method === 'cod') {
    const ok = await confirm.ask({
      title: t('track.codConfirmTitle'),
      message: t('track.codConfirmMsg'),
      confirmText: t('track.codConfirmYes'),
    })
    if (!ok) return
  }
  paying.value = method
  payErr.value = ''
  try {
    const q = props.token ? `?t=${encodeURIComponent(props.token)}` : ''
    const r = await api(`/orders/${props.order.id}/pay${q}`,
                        { method: 'POST', body: { method }, auth: true })
    if (r.redirect_url) { window.location.href = r.redirect_url; return }
    // The order is real now, and the basket has been holding these same items since
    // the payment was abandoned — that is deliberate, so an interrupted checkout can
    // be retried, but from here it would have them buying the lot a second time.
    // Only this order's lines: the basket may have moved on since.
    await takeOutOfBasket(cart, props.order.items)
    emit('changed')
  } catch (e) {
    payErr.value = e.message
    // 409 means it was released or settled while they were looking at it — the page
    // is out of date, and what it shows next matters more than the message
    if (e.status === 409) emit('changed')
  } finally {
    paying.value = ''
  }
}
</script>

<style scoped>
.items { list-style: none; margin: 1.6rem 0 0; text-align: start; }
.items li { display: flex; align-items: center; gap: .5rem; padding: .45rem 0; border-bottom: 1px solid rgba(60,74,39,.08); font-size: .92rem; }
.items .nm { flex: 1; }
.items .qt { font-size: .82rem; }
.items .pr { font-weight: 700; color: var(--terra-deep); white-space: nowrap; }
.totals { margin-top: .8rem; text-align: start; font-size: .9rem; }
.totals .row { display: flex; justify-content: space-between; gap: .6rem; padding: .18rem 0; }
.totals .total { font-weight: 700; border-top: 1px solid rgba(60,74,39,.12); margin-top: .3rem; padding-top: .4rem; }
.owed { color: #b4862c; font-weight: 700; }
.settled { color: var(--green, #3c4a27); font-weight: 700; }

.released { margin: 1rem 0 .4rem; padding: .95rem 1rem; border-radius: 14px;
  background: rgba(156,43,43,.07); border: 1px solid rgba(156,43,43,.25); }
.released h2 { font-family: 'Amiri', serif; color: var(--green, #3c4a27); font-size: 1.05rem; margin: 0 0 .3rem; }
.released .a-muted { font-size: .84rem; line-height: 1.5; margin: 0 0 .7rem; }
.paynow { margin: 1rem 0 .4rem; padding: .95rem 1rem; border-radius: 14px;
  background: rgba(184,144,47,.10); border: 1px solid rgba(184,144,47,.38); }
.paynow h2 { font-family: 'Amiri', serif; color: var(--green, #3c4a27); font-size: 1.05rem; margin: 0 0 .3rem; }
.paynow .a-muted { font-size: .84rem; line-height: 1.5; margin: 0 0 .7rem; }
.paynow-amount { font-family: 'Amiri', serif; font-size: 1.5rem; font-weight: 700;
  color: var(--green, #3c4a27); margin: 0 0 .7rem; }
.paynow-acts { display: flex; gap: .5rem; flex-wrap: wrap; }
.paynow-acts .btn { flex: 1 1 auto; font-size: .86rem; padding: .6rem 1rem; }
.btn-ghost { background: #fff; color: var(--green, #3c4a27); border: 1px solid rgba(60,74,39,.3); }
.paynow .err { color: var(--red, #9c2b2b); font-size: .82rem; margin: 0 0 .5rem; }

.deliv { margin-top: 1.4rem; text-align: start; background: var(--cream-2); border-radius: 14px; padding: .8rem 1rem; }
.deliv h2 { font-size: .82rem; color: var(--green); margin-bottom: .3rem; letter-spacing: .03em; }
.deliv p { font-size: .88rem; }
.help { margin: 1.3rem 0 .7rem; font-size: .84rem; text-align: center; }
.wa { display: inline-flex; }

/* Inside a list card: the same content, tightened, and opened on request. */
.compact .items { margin-top: .7rem; }
.compact .items li { font-size: .86rem; padding: .3rem 0; }
.compact .totals { font-size: .84rem; }
.compact .released, .compact .paynow { padding: .7rem .85rem; border-radius: 12px; }
.compact .released h2, .compact .paynow h2 { font-size: .95rem; }
.compact .paynow-amount { font-size: 1.2rem; }
.compact .deliv { margin-top: .8rem; padding: .6rem .8rem; }
.compact .help { margin: .8rem 0 .5rem; font-size: .8rem; text-align: start; }
.compact .wa { font-size: .8rem; padding: .4rem .85rem; }
.od-toggle {
  display: block; margin: .55rem 0 0; padding: 0;
  background: none; border: 0; color: var(--green);
  font: inherit; font-size: .8rem; font-weight: 700;
  text-decoration: underline; cursor: pointer;
}
</style>
