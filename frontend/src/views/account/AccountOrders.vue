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
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'
import Loader from '../../components/Loader.vue'
import OrderTimeline from '../../components/OrderTimeline.vue'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'

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
  if (o.payment_method === 'ziina') return o.payment_status === 'paid' ? t('account.paidOnline') : t('account.awaitingPayment')
  return o.status === 'delivered' ? t('account.paidOnDelivery') : t('checkout.cod')
}
const fmtDate = (d) => new Date(d).toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })

onMounted(() => ordersStore.fetch())
</script>

<style scoped>
.panel { background: #fff; border-radius: 18px; padding: 1.4rem; margin-top: 1.4rem; box-shadow: 0 8px 30px rgba(60,74,39,.06); }
.panel-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.35rem; margin-bottom: .8rem; }
.pay-line { margin-top: .5rem; font-size: .8rem; }
</style>
