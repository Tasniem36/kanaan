<template>
  <div class="tw">
    <div class="tcard">
      <RouterLink to="/" class="brand"><span class="g">دكّان</span> كنعان</RouterLink>

      <Loader v-if="loading" :label="t('common.loading')" />

      <template v-else-if="order">
        <span class="eyebrow">{{ t('track.eyebrow') }}</span>
        <h1 class="display">{{ t('track.title', { id: orderNumber(order) }) }}</h1>
        <p class="a-muted when">{{ fmtDate(order.created_at) }}</p>

        <!-- Everything below the heading is the same component طلباتي renders, so a
             guest and a signed-in customer read the same order the same way. -->
        <OrderDetails :order="order" :token="tokenOf()" @changed="load(order.id, tokenOf())" />
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
                <span class="mine-ref" dir="ltr">{{ orderNumber(o) }}</span>
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
import { ref, reactive, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../services/api'
import Loader from '../components/Loader.vue'
import OrderDetails from '../components/OrderDetails.vue'
import NeedHelp from '../components/NeedHelp.vue'
import { useMyOrdersStore } from '../stores/myOrders'
import { dateTime } from '../utils/datetime'
import { orderNumber, statusLabelKey } from '../utils/order'

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

// The status badge on the طلباتي rows below the lookup form — the one place this
// page still labels an order itself. Everything about an opened order is said by
// OrderDetails, so the two pages cannot word it differently.
const statusLabel = (o) => t(statusLabelKey(o))

const tokenOf = () => String(route.query.t || '')

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

const fmtDate = (d) => dateTime(d, locale.value)

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
/* the lookup form's hint — the order's own detail styles live in OrderDetails.vue */
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
