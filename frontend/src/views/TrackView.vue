<template>
  <div class="tw">
    <div class="tcard">
      <RouterLink to="/" class="brand"><span class="g">دكّان</span> كنعان</RouterLink>

      <Loader v-if="loading" :label="t('common.loading')" />

      <template v-else-if="order">
        <span class="eyebrow">{{ t('track.eyebrow') }}</span>
        <h1 class="display">{{ t('track.title', { id: order.number }) }}</h1>
        <p class="a-muted when">{{ fmtDate(order.created_at) }}</p>

        <OrderTimeline :status="order.status" :events="order.events" />

        <ul class="items">
          <li v-for="(it, i) in order.items" :key="i">
            <span class="nm">{{ it.name }}</span>
            <span class="a-muted qt">×{{ it.qty }}</span>
            <span class="pr">{{ money(it.price * it.qty) }} <span class="dh" role="img" aria-label="درهم"></span></span>
          </li>
        </ul>

        <div class="totals">
          <div v-if="Number(order.discount_amount) > 0" class="row">
            <span class="a-muted">{{ t('checkout.discountLine') }}</span>
            <span style="color:var(--red)">− {{ money(order.discount_amount) }} <span class="dh" role="img" aria-label="درهم"></span></span>
          </div>
          <div class="row">
            <span class="a-muted">{{ t('checkout.deliveryFee') }}</span>
            <span v-if="Number(order.delivery_fee) > 0">{{ money(order.delivery_fee) }} <span class="dh" role="img" aria-label="درهم"></span></span>
            <span v-else style="color:var(--green)">{{ t('checkout.freeDelivery') }}</span>
          </div>
          <div class="row total">
            <span>{{ t('checkout.total') }}</span>
            <span>{{ money(order.total) }} <span class="dh" role="img" aria-label="درهم"></span></span>
          </div>
          <!-- What actually happened to the money. Reading this off payment_method
               alone told somebody looking at an order they had never paid for that it
               was "الدفع الإلكتروني", with nothing to say it was still owed — the same
               mistake the confirmation e-mail used to make. -->
          <div class="row">
            <span class="a-muted">{{ t('checkout.payMethod') }}</span>
            <span :class="{ owed: awaitingPayment, settled: order.payment_status === 'paid' }">
              {{ payLabel }}
            </span>
          </div>
        </div>

        <section v-if="releasedUnpaid" class="released" aria-labelledby="rel-h">
          <h2 id="rel-h">{{ t('track.releasedTitle') }}</h2>
          <p class="a-muted">{{ t('track.releasedMsg') }}</p>
          <!-- Said separately and plainly: the first thing somebody thinks on
               reading "cancelled" is whether they have been charged for it. -->
          <p class="a-muted">{{ t('track.releasedReassure') }}</p>
          <RouterLink to="/" class="btn btn-green">{{ t('track.orderAgain') }}</RouterLink>
        </section>

        <!-- An abandoned card checkout leaves a real order that nobody has paid for,
             and this page is the only one its customer can reach. Their way back in
             used to be building the whole basket again. -->
        <section v-if="awaitingPayment" class="paynow" aria-labelledby="paynow-h">
          <h2 id="paynow-h">{{ t('track.awaitingTitle') }}</h2>
          <p class="a-muted">{{ t('track.awaitingMsg') }}</p>
          <!-- The amount stands on its own rather than inside the sentence: it is
               the one thing they need to recognise before choosing, and the same
               figure as the total above. -->
          <p class="paynow-amount">
            {{ money(order.total) }} <span class="dh" role="img" aria-label="درهم"></span>
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

        <div class="deliv">
          <h2>{{ t('track.deliverTo') }}</h2>
          <p>{{ order.customer_name }}<span v-if="order.phone_hint" class="a-muted" dir="ltr"> · {{ order.phone_hint }}</span></p>
          <p class="a-muted">{{ t('account.addrLine', { city: order.city, street: order.street, house: order.house }) }}</p>
          <p v-if="order.notes" class="a-muted">{{ order.notes }}</p>
        </div>

        <p class="a-muted help">{{ t('track.wrongDetails') }}</p>
        <a class="btn btn-green" :href="whatsappLink(waText)" target="_blank" rel="noopener">{{ t('track.whatsapp') }}</a>
      </template>

      <!-- No id in the URL, or a link that didn't open anything: look the order up
           from the number on the confirmation e-mail plus a contact detail. -->
      <template v-else>
        <span class="eyebrow">{{ t('track.eyebrow') }}</span>
        <h1 class="display">{{ hadLink ? t('track.notFoundTitle') : t('track.lookupTitle') }}</h1>
        <p class="a-muted">{{ hadLink ? t('track.notFoundMsg') : t('track.lookupMsg') }}</p>

        <!-- Orders placed from this device, gathered without an account: each one
             carries its own tracking token, which is all the status page needs. See
             stores/myOrders.js for what this is and isn't. -->
        <section v-if="myOrders.count" class="mine" aria-labelledby="mine-h">
          <h2 id="mine-h">{{ t('track.mineTitle') }}</h2>
          <ul>
            <li v-for="o in myOrders.list" :key="o.id">
              <RouterLink :to="{ name: 'track', params: { id: o.id }, query: { t: o.token } }" class="mine-row">
                <span class="mine-ref" dir="ltr">{{ o.number || refOf(o) }}</span>
                <span class="mine-when a-muted">{{ fmtDate(o.created_at || o.at) }}</span>
                <span v-if="o.status" class="mine-status" :class="'s-' + o.status">{{ statusLabel(o) }}</span>
                <span v-else-if="myOrders.loading" class="mine-status a-muted">…</span>
              </RouterLink>
            </li>
          </ul>
          <p class="a-muted mine-note">{{ t('track.mineNote') }}</p>
        </section>

        <form class="lookup" @submit.prevent="lookup">
          <label class="co-l" for="lk-ref">{{ t('track.orderNumber') }}</label>
          <input id="lk-ref" class="a-input" v-model.trim="form.ref" dir="ltr" placeholder="DK-K7M2XPQ" autocomplete="off">
          <label class="co-l" for="lk-contact">{{ t('track.contact') }}</label>
          <input id="lk-contact" class="a-input" v-model.trim="form.contact" dir="ltr" placeholder="050 123 4567">
          <p v-if="lookupErr" class="err">{{ lookupErr }}</p>
          <button class="btn btn-green" type="submit" :disabled="finding">
            {{ finding ? t('common.loading') : t('track.findOrder') }}
          </button>
        </form>

        <p class="a-muted help">{{ t('track.lookupHint') }}</p>
        <!-- They have an order number and still cannot reach their order: a lost
             e-mail, a typo, or the wrong phone on the order. Only the shop can fix
             any of those, so stop asking them to guess and put them in touch. -->
        <NeedHelp v-if="lookupErr" where="track_lookup" :subject="t('help.orderSubject')" />
        <RouterLink to="/" class="back">{{ t('pay.backHome') }}</RouterLink>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../services/api'
import Loader from '../components/Loader.vue'
import OrderTimeline from '../components/OrderTimeline.vue'
import NeedHelp from '../components/NeedHelp.vue'
import { whatsappLink } from '../utils/contact'
import { useMyOrdersStore } from '../stores/myOrders'
import { useCartStore } from '../stores/cart'
import { dateTime } from '../utils/datetime'

// Public order status page. The token in the URL is the credential — no account
// needed, which is the whole point for a guest who checked out without one.
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const order = ref(null)
const loading = ref(true)
// a link was followed but didn't open an order → show "not found" above the form
const hadLink = ref(false)
const form = reactive({ ref: '', contact: '' })
const finding = ref(false)
const lookupErr = ref('')
const myOrders = useMyOrdersStore()
const cart = useCartStore()

// 'pending' means two different things: a cash order being processed, and a card
// order still waiting to be paid. OrderTimeline draws the same distinction.
const statusLabel = (o) => t(o.status === 'pending' && o.payment_method === 'cod'
  ? 'status.pendingCod' : 'status.' + o.status)
// Awaiting payment: a card order that was never paid for and is still alive. Cash
// orders are unpaid by definition until they are handed over, and a released order
// has had its stock put back — neither is something to collect money for here.
const awaitingPayment = computed(() => !!order.value
  && order.value.payment_status !== 'paid'
  && order.value.payment_method !== 'cod'
  && order.value.status !== 'cancelled')

const payLabel = computed(() => {
  const o = order.value
  if (!o) return ''
  if (o.payment_method === 'cod') return t('checkout.cod')
  if (o.payment_status === 'paid') return t('track.paidOnline')
  // "awaiting payment" on a released order is not true any more — nobody is waiting
  // for it, the shop has taken the goods back
  return o.status === 'cancelled' ? t('track.notPaid') : t('track.awaitingPayment')
})

// Released for not being paid for. The sweep says so in the shop's log but tells the
// customer nothing, so without this they come back to a cancelled order and no reason
// for it — and this is exactly the screen somebody lands on when they took too long.
const releasedUnpaid = computed(() => !!order.value
  && order.value.status === 'cancelled'
  && order.value.payment_status !== 'paid'
  && order.value.payment_method !== 'cod')

const paying = ref('')
const payErr = ref('')

// Card sends them back to the payment page they walked away from; cash turns this
// into an ordinary cash-on-delivery order, which is also what takes it out of the
// sweep that would otherwise cancel it. Either way the page reloads and says what
// the order now is, rather than assuming the answer.
async function choosePayment(method) {
  paying.value = method
  payErr.value = ''
  try {
    const r = await api(`/orders/${order.value.id}/pay?t=${encodeURIComponent(tokenOf())}`,
                        { method: 'POST', body: { method }, auth: true })
    if (r.redirect_url) { window.location.href = r.redirect_url; return }
    // The order is real now, and the basket has been holding these same items since
    // the payment was abandoned — that is deliberate, so an interrupted checkout can
    // be retried, but from here it would have them buying the lot a second time.
    // Only this order's lines: the basket may have moved on since.
    await cart.whenSynced()
    cart.removeOrdered(order.value.items)
    await load(order.value.id, tokenOf())
  } catch (e) {
    payErr.value = e.message
    // 409 means it was released or settled while they were looking at it — the page
    // is out of date, and what it shows next matters more than the message
    if (e.status === 409) await load(order.value.id, tokenOf())
  } finally {
    paying.value = ''
  }
}

const tokenOf = () => String(route.query.t || '')

// the order number, before the live one has arrived
const refOf = (o) => (o.ref ? `DK-${o.ref}` : `#${String(o.id).slice(0, 8)}`)

// Exchange the order number + a contact detail for the order's own tracking link,
// then show it the same way the e-mailed link does.
async function lookup() {
  lookupErr.value = ''
  if (!form.ref || !form.contact) { lookupErr.value = t('track.lookupRequired'); return }
  finding.value = true
  try {
    const { id, token } = await api('/orders/lookup', { method: 'POST', body: { ...form } })
    // Normally the route watcher loads it — see the bottom of this file. But looking up
    // the order that's already in the address bar changes nothing about the route, so
    // the watcher wouldn't fire and the button would look dead: load it here instead.
    const sameOrder = String(route.params.id || '') === String(id)
      && String(route.query.t || '') === String(token)
    if (sameOrder) {
      hadLink.value = true
      await load(id, token)
    } else {
      await router.replace({ name: 'track', params: { id }, query: { t: token } })
    }
  } catch (e) {
    lookupErr.value = e.message
  } finally {
    finding.value = false
  }
}

async function load(id, token) {
  loading.value = true
  try {
    const { order: row } = await api(
      `/orders/track/${id}?t=${encodeURIComponent(String(token || ''))}`,
      { auth: true }) // a signed-in customer opening their own order works without the token
    order.value = row
  } catch {
    order.value = null // wrong/expired link — the form below lets them look it up
  } finally {
    loading.value = false
  }
}

const money = (n) => new Intl.NumberFormat(locale.value === 'ar' ? 'ar-AE' : 'en-AE',
  { maximumFractionDigits: 2 }).format(Number(n || 0))
const fmtDate = (d) => dateTime(d, locale.value)
// whatsappLink encodes it, so this is the plain sentence
const waText = computed(() => t('track.whatsappText', { id: order.value?.number || '' }))

// Driven by the route, not by mount: opening an order from the طلباتي list goes
// /track → /track/:id, which is the same component, so no mount hook fires again and
// the page would sit on the form. The lookup form's redirect lands here too, which is
// why it doesn't load anything itself.
watch(() => [route.params.id, String(route.query.t || '')], ([id, tok]) => {
  if (!id) {
    // bare /track: the form, and above it whatever this device remembers ordering.
    // Statuses are fetched here and only here — no point costing requests on a page
    // opened straight to a single order.
    order.value = null
    hadLink.value = false
    loading.value = false
    myOrders.fetchStatuses()
    return
  }
  hadLink.value = true
  load(id, tok)
}, { immediate: true })
</script>

<style scoped>
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
.owed { color: #b4862c; font-weight: 700; }
.settled { color: var(--green, #3c4a27); font-weight: 700; }

.tw { min-height: 100vh; background: var(--cream); display: grid; place-items: start center; padding: 2.2rem 1.1rem 3rem; }
.tcard {
  width: min(560px, 100%); background: var(--paper);
  border: 1px solid rgba(60,74,39,.14); border-radius: 22px;
  padding: 1.8rem 1.5rem; text-align: center;
  box-shadow: 0 30px 60px -40px rgba(44,55,25,.5);
}
.brand { display: block; font-family: 'Aref Ruqaa', serif; font-size: 1.5rem; color: var(--green); margin-bottom: 1rem; }
.brand .g { color: var(--gold); }
h1 { font-size: clamp(1.4rem, 4vw, 1.9rem); color: var(--green); margin: .45rem 0 .2rem; }
.when { font-size: .82rem; margin-bottom: 1.4rem; }
.items { list-style: none; margin: 1.6rem 0 0; text-align: start; }
.items li { display: flex; align-items: center; gap: .5rem; padding: .45rem 0; border-bottom: 1px solid rgba(60,74,39,.08); font-size: .92rem; }
.items .nm { flex: 1; }
.items .qt { font-size: .82rem; }
.items .pr { font-weight: 700; color: var(--terra-deep); white-space: nowrap; }
.totals { margin-top: .8rem; text-align: start; font-size: .9rem; }
.totals .row { display: flex; justify-content: space-between; gap: .6rem; padding: .18rem 0; }
.totals .total { font-weight: 700; border-top: 1px solid rgba(60,74,39,.12); margin-top: .3rem; padding-top: .4rem; }
.deliv { margin-top: 1.4rem; text-align: start; background: var(--cream-2); border-radius: 14px; padding: .8rem 1rem; }
.deliv h2 { font-size: .82rem; color: var(--green); margin-bottom: .3rem; letter-spacing: .03em; }
.deliv p { font-size: .88rem; }
.help { margin: 1.3rem 0 .7rem; font-size: .84rem; }
/* طلباتي — what this device remembers ordering, above the lookup form */
.mine { margin: 1.6rem 0 .4rem; text-align: start; }
.mine h2 {
  font-size: .95rem; color: var(--green); margin-bottom: .5rem;
  text-align: center;
}
.mine ul { list-style: none; margin: 0; }
.mine li + li { margin-top: .4rem; }
.mine-row {
  display: flex; align-items: center; gap: .6rem;
  padding: .65rem .8rem;
  border: 1px solid rgba(60,74,39,.14); border-radius: 12px;
  font-size: .88rem;
  transition: border-color .15s, background .15s;
}
.mine-row:hover { border-color: var(--green); background: rgba(60,74,39,.04); }
.mine-ref { font-weight: 700; color: var(--green); }
.mine-when { font-size: .78rem; }
.mine-status {
  margin-inline-start: auto; font-size: .78rem; font-weight: 700;
  padding: .1rem .5rem; border-radius: 999px;
  background: rgba(60,74,39,.1); color: var(--green);
  white-space: nowrap;
}
.mine-status.s-delivered { background: rgba(60,74,39,.14); }
.mine-status.s-cancelled { background: rgba(156,43,43,.12); color: var(--red); }
.mine-note { font-size: .78rem; margin: .6rem 0 0; text-align: center; }

.lookup { text-align: start; margin: 1.4rem 0 .4rem; }
.lookup .btn { width: 100%; justify-content: center; margin-top: 1rem; }
.err { color: var(--red); font-size: .85rem; margin-top: .6rem; }
.back { display: inline-block; margin-top: .4rem; color: var(--green); text-decoration: underline; font-size: .88rem; }
</style>
