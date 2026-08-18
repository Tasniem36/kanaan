<template>
  <div class="tw">
    <div class="tcard">
      <RouterLink to="/" class="brand"><span class="g">دكّان</span> كنعان</RouterLink>

      <Loader v-if="loading" :label="t('common.loading')" />

      <template v-else-if="order">
        <span class="eyebrow">{{ t('track.eyebrow') }}</span>
        <h1 class="display">{{ t('track.title', { id: String(order.id).slice(0, 8) }) }}</h1>
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
          <div class="row">
            <span class="a-muted">{{ t('checkout.payMethod') }}</span>
            <span>{{ order.payment_method === 'cod' ? t('checkout.cod') : t('checkout.ziina') }}</span>
          </div>
        </div>

        <div class="deliv">
          <h2>{{ t('track.deliverTo') }}</h2>
          <p>{{ order.customer_name }}<span v-if="order.phone_hint" class="a-muted" dir="ltr"> · {{ order.phone_hint }}</span></p>
          <p class="a-muted">{{ t('account.addrLine', { city: order.city, street: order.street, house: order.house }) }}</p>
          <p v-if="order.notes" class="a-muted">{{ order.notes }}</p>
        </div>

        <p class="a-muted help">{{ t('track.wrongDetails') }}</p>
        <a class="btn btn-green" :href="`https://wa.me/971522981187?text=${waText}`" target="_blank" rel="noopener">{{ t('track.whatsapp') }}</a>
      </template>

      <template v-else>
        <h1 class="display">{{ t('track.notFoundTitle') }}</h1>
        <p class="a-muted">{{ t('track.notFoundMsg') }}</p>
        <RouterLink to="/" class="btn btn-green">{{ t('pay.backHome') }}</RouterLink>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../services/api'
import Loader from '../components/Loader.vue'
import OrderTimeline from '../components/OrderTimeline.vue'

// Public order status page. The token in the URL is the credential — no account
// needed, which is the whole point for a guest who checked out without one.
const { t, locale } = useI18n()
const route = useRoute()
const order = ref(null)
const loading = ref(true)

const money = (n) => new Intl.NumberFormat(locale.value === 'ar' ? 'ar-AE' : 'en-AE',
  { maximumFractionDigits: 2 }).format(Number(n || 0))
const fmtDate = (d) => new Date(d).toLocaleString(locale.value, { dateStyle: 'medium', timeStyle: 'short' })
const waText = computed(() => encodeURIComponent(
  t('track.whatsappText', { id: String(order.value?.id || '').slice(0, 8) })))

onMounted(async () => {
  try {
    const { order: row } = await api(
      `/orders/track/${route.params.id}?t=${encodeURIComponent(String(route.query.t || ''))}`,
      { auth: true }) // a signed-in customer opening their own order works without the token
    order.value = row
  } catch {
    order.value = null // wrong/expired link — the template shows the not-found state
  } finally {
    loading.value = false
  }
})
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
</style>
