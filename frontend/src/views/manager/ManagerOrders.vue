<template>
  <section>
    <div class="orders-head">
      <h1>{{ t('manager.allOrders') }}</h1>
      <button class="a-btn" :disabled="testing" @click="testNotify">{{ testing ? '…' : t('manager.testNotify') }}</button>
    </div>
    <Loader v-if="ordersStore.loading" :label="t('common.loading')" />
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('manager.noOrders') }}</p>

    <!-- orders grouped by customer -->
    <div class="cust-group" v-for="g in visibleGroups" :key="g.key">
      <div class="cust-head">
        <div><b>{{ g.name }}</b> · <span class="a-muted" dir="ltr">☎ {{ g.phone }}</span></div>
        <div class="a-muted">{{ g.orders.length }} {{ t('manager.ordersLabel') }} · {{ g.total }} <span class='dh' role='img' aria-label='درهم'></span></div>
      </div>

      <div class="a-card" v-for="o in g.orders" :key="o.id">
        <div class="a-row order-top">
          <div>
            <div><span style="font-family:monospace;color:var(--green)">#{{ o.id.slice(0, 8) }}</span> <span class="a-muted">· {{ fmtDate(o.created_at) }}</span></div>
            <div style="margin:.25rem 0"><span class="a-pill" :class="payClass(o)">{{ payLabel(o) }}</span></div>
            <div class="a-muted">📍 {{ t('manager.orderAddr', { city: o.city, street: o.street, house: o.house }) }}<span v-if="o.notes"> ({{ o.notes }})</span></div>
          </div>
          <div class="a-row order-ctrls" style="gap:.6rem">
            <span class="a-total">{{ o.total }} <span class='dh' role='img' aria-label='درهم'></span></span>
            <select class="a-status" :value="o.status" @change="changeStatus(o, $event.target.value)">
              <option value="pending">{{ t('status.pending') }}</option><option value="paid">{{ t('status.paid') }}</option><option value="fulfilled">{{ t('status.fulfilled') }}</option><option value="cancelled">{{ t('status.cancelled') }}</option>
            </select>
          </div>
        </div>
        <div style="margin-top:.5rem;border-top:1px solid rgba(60,74,39,.1);padding-top:.4rem">
          <div class="a-row" v-for="(it, ix) in o.items" :key="ix" style="font-size:.88rem;padding:.1rem 0">
            <span>{{ it.name }} × {{ it.qty }}</span><span class="a-muted">{{ it.price * it.qty }} <span class='dh' role='img' aria-label='درهم'></span></span>
          </div>
          <div v-if="Number(o.delivery_fee) > 0" class="a-row" style="font-size:.88rem;padding:.1rem 0"><span class="a-muted">{{ t('checkout.deliveryFee') }}</span><span class="a-muted">{{ o.delivery_fee }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
        </div>
      </div>
    </div>
    <div v-if="hasMore" ref="sentinel" class="load-more"><span class="ld-spin"></span></div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'
import { useToastStore } from '../../stores/toast'
import Loader from '../../components/Loader.vue'
import { api } from '../../services/api'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'

const { t, locale } = useI18n()
const ordersStore = useOrdersStore()
const toast = useToastStore()
const testing = ref(false)

function payLabel(o) {
  if (o.payment_method === 'ziina') return o.payment_status === 'paid' ? t('manager.payZiinaPaid') : t('manager.payZiinaUnpaid')
  return t('manager.payCod')
}
function payClass(o) {
  if (o.payment_method === 'ziina') return o.payment_status === 'paid' ? 'pill-ok' : 'pill-low'
  return 'pill-warn'
}

async function testNotify() {
  testing.value = true
  try {
    const r = await api('/orders/notify-test', { method: 'POST' })
    if (r.ok) toast.show(t('manager.testSent'))
    else if (!r.configured) toast.show(t('manager.testNotConfigured'))
    else toast.show(t('manager.testFailed', { e: r.error || '' }))
  } catch (e) {
    toast.show(e.message)
  } finally {
    testing.value = false
  }
}

// group orders by customer (account id, else phone); preserves newest-first order
const groups = computed(() => {
  const map = new Map()
  for (const o of ordersStore.orders) {
    const key = o.user_id || o.phone || o.id
    if (!map.has(key)) map.set(key, { key, name: o.customer_name, phone: o.phone, orders: [], total: 0 })
    const g = map.get(key)
    g.orders.push(o)
    g.total += Number(o.total)
  }
  return [...map.values()]
})

const { visible: visibleGroups, sentinel, hasMore } = useInfiniteScroll(() => groups.value, 10)

const fmtDate = (d) => new Date(d).toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })

async function changeStatus(o, status) {
  try { await ordersStore.setStatus(o.id, status); toast.show(t('manager.toastStatus')) }
  catch (e) { toast.show(e.message) }
}

onMounted(() => ordersStore.fetch())
</script>

<style scoped>
.orders-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; }
.cust-group { margin-bottom: 1.8rem; }
.cust-head { display: flex; justify-content: space-between; align-items: center; gap: .6rem; flex-wrap: wrap; padding: .5rem .2rem; margin-bottom: .5rem; border-bottom: 2px solid rgba(60,74,39,.15); }
.cust-head b { color: var(--green); font-size: 1.05rem; }
.a-status { max-width: 100%; }
/* on phones, stack the card: info on top, then total + status on their own row */
@media (max-width: 560px) {
  .order-top { flex-direction: column; align-items: stretch; gap: .6rem; }
  .order-ctrls { width: 100%; justify-content: space-between; }
  .order-ctrls .a-status { flex: 1 1 auto; min-width: 0; }
}
</style>
