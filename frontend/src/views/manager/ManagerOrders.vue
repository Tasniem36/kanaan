<template>
  <section>
    <div class="orders-head">
      <h1>{{ t('manager.allOrders') }}</h1>
      <button class="a-btn" :disabled="testing" @click="testNotify">{{ testing ? '…' : t('manager.testNotify') }}</button>
    </div>
    <Loader v-if="ordersStore.loading && !ordersStore.orders.length" :label="t('common.loading')" />
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('manager.noOrders') }}</p>

    <template v-else>
      <!-- status tabs -->
      <div class="otabs">
        <button v-for="tab in STATUS_TABS" :key="tab.key" class="otab" :class="{ on: activeTab === tab.key }" @click="activeTab = tab.key">
          {{ t(tab.label) }} <span class="otab-cnt">{{ counts[tab.key] }}</span>
        </button>
      </div>
      <!-- payment-type filter -->
      <div class="pfilter">
        <button class="pchip" :class="{ on: payFilter === 'all' }" @click="payFilter = 'all'">{{ t('manager.payAll') }}</button>
        <button class="pchip" :class="{ on: payFilter === 'cod' }" @click="payFilter = 'cod'">{{ t('manager.payCod') }}</button>
        <button class="pchip" :class="{ on: payFilter === 'ziina' }" @click="payFilter = 'ziina'">{{ t('manager.payZiina') }}</button>
      </div>

      <p v-if="!visibleGroups.length" class="a-muted">{{ t('manager.noOrdersFilter') }}</p>
    </template>

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
import { ref, computed, watch, onMounted } from 'vue'
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

// status tabs: new (needs shipping), shipped, cancelled
const STATUS_TABS = [
  { key: 'new', label: 'manager.tabNew', statuses: ['pending', 'paid'] },
  { key: 'shipped', label: 'manager.tabShipped', statuses: ['fulfilled'] },
  { key: 'cancelled', label: 'manager.tabCancelled', statuses: ['cancelled'] },
]
const activeTab = ref('new')
const payFilter = ref('all') // all | cod | ziina

const matchesPay = (o) => payFilter.value === 'all' || o.payment_method === payFilter.value
const tabStatuses = computed(() => STATUS_TABS.find((tb) => tb.key === activeTab.value)?.statuses || [])

// per-tab counts, respecting the active payment filter
const counts = computed(() => {
  const c = { new: 0, shipped: 0, cancelled: 0 }
  for (const o of ordersStore.orders) {
    if (!matchesPay(o)) continue
    const tab = STATUS_TABS.find((tb) => tb.statuses.includes(o.status))
    if (tab) c[tab.key]++
  }
  return c
})

// group the filtered orders by customer (account id, else phone); newest-first
const groups = computed(() => {
  const map = new Map()
  for (const o of ordersStore.orders) {
    if (!tabStatuses.value.includes(o.status) || !matchesPay(o)) continue
    const key = o.user_id || o.phone || o.id
    if (!map.has(key)) map.set(key, { key, name: o.customer_name, phone: o.phone, orders: [], total: 0 })
    const g = map.get(key)
    g.orders.push(o)
    g.total += Number(o.total)
  }
  return [...map.values()]
})

const { visible: visibleGroups, sentinel, hasMore, reset } = useInfiniteScroll(() => groups.value, 10)
// restart paging from the top whenever the tab or payment filter changes
watch([activeTab, payFilter], reset)

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
/* status tabs */
.otabs { display: flex; gap: .4rem; flex-wrap: wrap; border-bottom: 2px solid rgba(60,74,39,.12); margin-bottom: .8rem; }
.otab {
  padding: .55rem 1.1rem; background: transparent; border: none; cursor: pointer;
  font-family: inherit; font-size: .95rem; font-weight: 600; color: var(--muted);
  border-bottom: 3px solid transparent; margin-bottom: -2px; display: inline-flex; align-items: center; gap: .45rem;
}
.otab:hover { color: var(--green); }
.otab.on { color: var(--green); border-bottom-color: var(--green); }
.otab-cnt {
  font-size: .78rem; font-weight: 700; min-width: 20px; padding: 0 .35rem; height: 20px;
  display: inline-grid; place-items: center; border-radius: 999px;
  background: var(--cream-2, rgba(60,74,39,.1)); color: var(--green);
}
.otab.on .otab-cnt { background: var(--green); color: #fff; }
/* payment-type filter */
.pfilter { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: 1.4rem; }
.pchip {
  padding: .35rem .9rem; border-radius: 999px; border: 1.5px solid rgba(60,74,39,.2);
  background: transparent; color: var(--green); font-family: inherit; font-size: .85rem; font-weight: 600; cursor: pointer;
}
.pchip:hover { border-color: var(--green); }
.pchip.on { background: var(--green); color: #fff; border-color: var(--green); }
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
