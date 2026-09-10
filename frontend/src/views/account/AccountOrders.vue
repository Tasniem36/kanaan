<template>
  <section class="panel">
    <div class="panel-head"><h2>{{ t('account.orders') }}</h2></div>
    <Loader v-if="ordersStore.loading" :label="t('common.loading')" />
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('account.noOrders') }} <RouterLink to="/" style="color:var(--green);text-decoration:underline">{{ t('account.shopNow') }}</RouterLink></p>
    <div v-else>
      <div class="a-card" v-for="o in visibleOrders" :key="o.id">
        <div class="a-row">
          <div>
            <span style="font-family:monospace;color:var(--green)">#{{ o.id.slice(0, 8) }}</span>
            <span class="a-muted"> · {{ fmtDate(o.created_at) }}</span>
          </div>
          <div class="a-row" style="gap:.6rem">
            <span class="a-total">{{ o.total }} <span class='dh' role='img' aria-label='درهم'></span></span>
            <span class="a-pill" :class="statusClass(o.status)">{{ statusLabel(o) }}</span>
          </div>
        </div>
        <OrderTimeline :status="o.status" :events="o.events || []" />
        <p class="a-muted pay-line">{{ payLabel(o) }}</p>
        <!-- Saying "awaiting payment" and offering nothing to do about it leaves the
             customer to rebuild the basket from scratch. Same two ways out as the
             tracking page, and the same wording, so they cannot drift apart. -->
        <div v-if="awaiting(o)" class="pay-acts">
          <button class="a-btn pay-card" :disabled="!!paying" @click="choosePayment(o, 'ziina')">
            {{ paying === o.id + ':ziina' ? t('common.loading') : t('track.payNow') }}
          </button>
          <button class="a-btn" :disabled="!!paying" @click="choosePayment(o, 'cod')">
            {{ paying === o.id + ':cod' ? t('common.loading') : t('track.payOnDelivery') }}
          </button>
        </div>
        <p v-if="payErr[o.id]" class="pay-err">{{ payErr[o.id] }}</p>
        <div style="margin-top:.4rem;border-top:1px solid rgba(60,74,39,.1);padding-top:.4rem">
          <div class="a-row" v-for="(it, ix) in o.items" :key="ix" style="font-size:.88rem;padding:.1rem 0">
            <span>{{ it.name }} × {{ it.qty }}</span><span class="a-muted">{{ it.price * it.qty }} <span class='dh' role='img' aria-label='درهم'></span></span>
          </div>
          <div v-if="Number(o.delivery_fee) > 0" class="a-row" style="font-size:.88rem;padding:.1rem 0"><span class="a-muted">{{ t('checkout.deliveryFee') }}</span><span class="a-muted">{{ o.delivery_fee }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
        </div>
      </div>
      <div v-if="hasMore" ref="sentinel" class="load-more"><span class="ld-spin"></span></div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'
import Loader from '../../components/Loader.vue'
import OrderTimeline from '../../components/OrderTimeline.vue'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { longDate } from '../../utils/datetime'
import { api } from '../../services/api'
import { useCartStore } from '../../stores/cart'
import { useConfirmStore } from '../../stores/confirm'
import { takeOutOfBasket } from '../../services/awaitingPayment'

const { t, locale } = useI18n()
const ordersStore = useOrdersStore()

const { visible: visibleOrders, sentinel, hasMore } = useInfiniteScroll(() => ordersStore.orders, 10)

// "Awaiting payment" is only true for an unpaid online order. On cash on
// delivery there is nothing to await, so it reads as processing instead.
const statusLabel = (o) =>
  o.status === 'pending' && o.payment_method !== 'ziina' ? t('status.pendingCod') : t(`status.${o.status}`)
const statusClass = (s) => ({ pending: 'pill-warn', paid: 'pill-ok', preparing: 'pill-warn', fulfilled: 'pill-ok', delivered: 'pill-ok', cancelled: 'pill-low' }[s] || '')

// Payment shown from the payment fields alone — never derived from how far the
// order has travelled.
const payLabel = (o) => {
  if (o.payment_method === 'ziina') {
    if (o.payment_status === 'paid') return t('account.paidOnline')
    // Nobody is awaiting payment for an order that was released — the shop took the
    // goods back. Saying otherwise next to a red ملغى pill reads as a bill still owed.
    return o.status === 'cancelled' ? t('track.notPaid') : t('account.awaitingPayment')
  }
  return o.status === 'delivered' ? t('account.paidOnDelivery') : t('checkout.cod')
}
const fmtDate = (d) => longDate(d, locale.value)

// An online order nobody has paid for, and still alive. Cash is unpaid by definition
// until it is handed over, and a cancelled order has had its stock put back.
const awaiting = (o) => o.payment_method === 'ziina'
  && o.payment_status !== 'paid' && o.status !== 'cancelled'

const cart = useCartStore()
const confirm = useConfirmStore()
const paying = ref('')          // "<order id>:<method>", so one row's spinner is its own
const payErr = reactive({})

async function choosePayment(o, method) {
  // Cash commits: the order goes to the shop to prepare, and these buttons go away
  // because there is no longer a payment waiting to be finished. Card does not — a
  // payment page nobody completes changes nothing — so only this one asks.
  if (method === 'cod') {
    const ok = await confirm.ask({
      title: t('track.codConfirmTitle'),
      message: t('track.codConfirmMsg'),
      confirmText: t('track.codConfirmYes'),
    })
    if (!ok) return
  }
  paying.value = `${o.id}:${method}`
  payErr[o.id] = ''
  try {
    // no tracking token needed: this page is behind a session, and the order is theirs
    const r = await api(`/orders/${o.id}/pay`, { method: 'POST', body: { method }, auth: true })
    if (r.redirect_url) { window.location.href = r.redirect_url; return }
    // Cash: the order is real now, so its lines come out of the basket — which has
    // been holding them since the payment was abandoned.
    await takeOutOfBasket(cart, o.items)
    await ordersStore.fetch({ mine: true })
  } catch (e) {
    payErr[o.id] = e.message
    if (e.status === 409) await ordersStore.fetch()   // released or settled meanwhile
  } finally {
    paying.value = ''
  }
}

onMounted(() => ordersStore.fetch({ mine: true }))
</script>

<style scoped>
.panel { background: #fff; border-radius: 18px; padding: 1.4rem; margin-top: 1.4rem; box-shadow: 0 8px 30px rgba(60,74,39,.06); }
.panel-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.35rem; margin-bottom: .8rem; }
.pay-line { margin-top: .5rem; font-size: .8rem; }
.pay-acts { display: flex; gap: .45rem; flex-wrap: wrap; margin-top: .5rem; }
.pay-acts .a-btn { font-size: .8rem; padding: .4rem .85rem; border-radius: 999px;
  background: #fff; color: var(--green); border: 1px solid rgba(60,74,39,.3); font-weight: 700; }
.pay-acts .pay-card { background: var(--green); color: #fff; border-color: var(--green); }
.pay-err { color: var(--red, #9c2b2b); font-size: .78rem; margin-top: .35rem; }
</style>
