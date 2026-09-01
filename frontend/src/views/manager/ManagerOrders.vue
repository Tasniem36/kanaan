<template>
  <section>
    <div class="orders-head">
      <h1>{{ t('manager.allOrders') }}</h1>
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

      <div
        class="a-card o-card" v-for="o in g.orders" :key="o.id"
        role="button" tabindex="0" :aria-label="t('manager.detailsTitle')"
        @click="detailId = o.id" @keydown.enter.prevent="detailId = o.id" @keydown.space.prevent="detailId = o.id"
      >
        <div class="a-row order-top">
          <div>
            <div><span style="font-family:monospace;color:var(--green)">#{{ o.id.slice(0, 8) }}</span> <span class="a-muted">· {{ fmtDate(o.created_at) }}</span></div>
            <div style="margin:.25rem 0"><span class="a-pill" :class="payClass(o)">{{ payLabel(o) }}</span></div>
            <div class="a-muted">📍 {{ t('manager.orderAddr', { city: o.city, street: o.street, house: o.house }) }}<span v-if="o.notes"> ({{ o.notes }})</span></div>
          </div>
          <div class="a-row order-ctrls" style="gap:.6rem" @click.stop @keydown.stop>
            <span class="a-total">{{ o.total }} <span class='dh' role='img' aria-label='درهم'></span></span>
            <select class="a-status" :value="o.status" @change="changeStatus(o, $event)">
              <option value="pending">{{ t('status.pending') }}</option><option value="paid">{{ t('status.paid') }}</option><option value="preparing">{{ t('status.preparing') }}</option><option value="fulfilled">{{ t('status.fulfilled') }}</option><option value="delivered">{{ t('status.delivered') }}</option><option value="cancelled">{{ t('status.cancelled') }}</option>
            </select>
            <button class="o-del" @click="deleteOrder(o)" :title="t('manager.delOrderTitle')" :aria-label="t('manager.delOrderTitle')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>
            </button>
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

    <!-- full order details: who to call, what to deliver, where -->
    <Dialog :open="!!detail" :title="t('manager.detailsTitle')" max-width="560px" @close="detailId = null">
      <template v-if="detail">
        <div class="d-head">
          <span style="font-family:monospace;color:var(--green)">#{{ detail.id.slice(0, 8) }}</span>
          <span class="a-muted">{{ fmtDate(detail.created_at) }}</span>
          <span class="a-pill" :class="statusClass(detail.status)">{{ t(`status.${detail.status}`) }}</span>
        </div>

        <!-- contact the customer -->
        <h4 class="d-sec">{{ t('manager.customerInfo') }}</h4>
        <div class="d-box">
          <div class="d-name">
            {{ detail.customer_name }}
            <span class="a-pill" :class="detail.user_id ? 'pill-ok' : 'pill-warn'">{{ detail.user_id ? t('manager.registered') : t('manager.guest') }}</span>
          </div>
          <div class="d-phone" dir="ltr">{{ detail.phone }}</div>
          <div v-if="detail.customer_email" class="a-muted" dir="ltr">{{ detail.customer_email }}</div>
          <div class="d-actions">
            <a class="d-act call" :href="`tel:${detail.phone}`">☎ {{ t('manager.call') }}</a>
            <a class="d-act wa" :href="waLink(detail)" target="_blank" rel="noopener">💬 {{ t('manager.whatsapp') }}</a>
            <button class="d-act copy" @click="copyPhone(detail.phone)">⧉ {{ t('manager.copyPhone') }}</button>
          </div>
        </div>

        <!-- where it goes -->
        <h4 class="d-sec">{{ t('manager.deliveryInfo') }}</h4>
        <div class="d-box">
          <div>📍 {{ t('manager.orderAddr', { city: detail.city, street: detail.street, house: detail.house }) }}</div>
          <div v-if="detail.notes" class="d-note">📝 {{ detail.notes }}</div>
        </div>

        <!-- what's in it -->
        <h4 class="d-sec">{{ t('manager.orderItems') }}</h4>
        <div class="d-box">
          <div class="a-row d-line" v-for="(it, ix) in detail.items" :key="ix">
            <span>{{ it.name }} × {{ it.qty }}</span><span class="a-muted">{{ money(it.price * it.qty) }} <span class='dh' role='img' aria-label='درهم'></span></span>
          </div>
          <div class="a-row d-line d-sum"><span class="a-muted">{{ t('manager.subtotal') }}</span><span class="a-muted">{{ money(subtotal) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
          <div v-if="Number(detail.discount_amount) > 0" class="a-row d-line"><span class="a-muted">{{ t('manager.discountLine', { code: detail.discount_code || '—' }) }}</span><span class="a-muted">− {{ money(detail.discount_amount) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
          <div v-if="Number(detail.delivery_fee) > 0" class="a-row d-line"><span class="a-muted">{{ t('checkout.deliveryFee') }}</span><span class="a-muted">{{ money(detail.delivery_fee) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
          <div class="a-row d-line d-total"><span>{{ t('manager.totalLine') }}</span><span class="a-total">{{ money(detail.total) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
        </div>

        <!-- how it was paid -->
        <h4 class="d-sec">{{ t('manager.paymentInfo') }}</h4>
        <div class="d-box">
          <span class="a-pill" :class="payClass(detail)">{{ payLabel(detail) }}</span>
        </div>

        <!-- how it got here -->
        <template v-if="detail.events && detail.events.length">
          <h4 class="d-sec">{{ t('manager.timeline') }}</h4>
          <ol class="d-time">
            <li v-for="(ev, ix) in detail.events" :key="ix">
              <span>{{ t(`status.${ev.status}`) }}</span>
              <span class="a-muted">{{ fmtDate(ev.created_at) }}</span>
            </li>
          </ol>
        </template>
      </template>
    </Dialog>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'
import Loader from '../../components/Loader.vue'
import Dialog from '../../components/Dialog.vue'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'

const { t, locale } = useI18n()
const ordersStore = useOrdersStore()
const toast = useToastStore()
const confirm = useConfirmStore()

function payLabel(o) {
  if (o.payment_method === 'ziina') return o.payment_status === 'paid' ? t('manager.payZiinaPaid') : t('manager.payZiinaUnpaid')
  return t('manager.payCod')
}
function payClass(o) {
  if (o.payment_method === 'ziina') return o.payment_status === 'paid' ? 'pill-ok' : 'pill-low'
  return 'pill-warn'
}
const statusClass = (s) => ({ pending: 'pill-warn', paid: 'pill-ok', preparing: 'pill-warn', fulfilled: 'pill-ok', delivered: 'pill-ok', cancelled: 'pill-low' }[s] || '')

// details dialog — held by id, so the card keeps following the store (a status
// change made from the list stays in sync with the open dialog)
const detailId = ref(null)
const detail = computed(() => ordersStore.orders.find((o) => o.id === detailId.value) || null)
const subtotal = computed(() => (detail.value?.items || []).reduce((s, it) => s + Number(it.price) * Number(it.qty), 0))
const money = (n) => Math.round(Number(n) * 100) / 100

// wa.me wants bare international digits, no '+' or spaces. New orders are stored
// as +9715XXXXXXXX, but older rows may still hold a local 05… number.
function waDigits(phone) {
  let d = String(phone || '').replace(/\D/g, '')
  if (d.startsWith('00')) d = d.slice(2)
  return d.startsWith('971') ? d : '971' + d.replace(/^0+/, '')
}
// opens WhatsApp with the order already written out, so the manager just sends
const waLink = (o) => {
  const text = t('manager.waMessage', {
    name: o.customer_name,
    id: o.id.slice(0, 8),
    status: t(`status.${o.status}`),
  })
  return `https://wa.me/${waDigits(o.phone)}?text=${encodeURIComponent(text)}`
}

async function copyPhone(phone) {
  try { await navigator.clipboard.writeText(phone); toast.show(t('manager.phoneCopied')) }
  catch { toast.show(phone) }   // clipboard blocked (insecure context) → show it to copy by hand
}


// status tabs following the order lifecycle: new → preparing → shipped → delivered → cancelled
const STATUS_TABS = [
  { key: 'new', label: 'manager.tabNew', statuses: ['pending', 'paid'] },
  { key: 'preparing', label: 'manager.tabPreparing', statuses: ['preparing'] },
  { key: 'shipped', label: 'manager.tabShipped', statuses: ['fulfilled'] },
  { key: 'delivered', label: 'manager.tabDelivered', statuses: ['delivered'] },
  { key: 'cancelled', label: 'manager.tabCancelled', statuses: ['cancelled'] },
]
const activeTab = ref('new')
const payFilter = ref('all') // all | cod | ziina

const matchesPay = (o) => payFilter.value === 'all' || o.payment_method === payFilter.value
const tabStatuses = computed(() => STATUS_TABS.find((tb) => tb.key === activeTab.value)?.statuses || [])

// per-tab counts, respecting the active payment filter
const counts = computed(() => {
  const c = { new: 0, preparing: 0, shipped: 0, delivered: 0, cancelled: 0 }
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

// date + time of the order, in the manager's local timezone
const fmtDate = (d) => new Date(d).toLocaleString(locale.value, { dateStyle: 'medium', timeStyle: 'short' })

async function changeStatus(o, e) {
  const status = e.target.value
  if (status === o.status) return
  const ok = await confirm.ask({
    title: t('manager.statusConfirmTitle'),
    message: t('manager.statusConfirmMsg', { id: o.id.slice(0, 8), status: t(`status.${status}`) }),
    confirmText: t('manager.statusConfirmYes'),
  })
  if (!ok) { e.target.value = o.status; return }   // reverted → put the dropdown back
  try { await ordersStore.setStatus(o.id, status); toast.show(t('manager.toastStatus')) }
  catch (err) { toast.show(err.message); e.target.value = o.status }
}

async function deleteOrder(o) {
  const ok = await confirm.ask({
    title: t('manager.delOrderTitle'),
    message: t('manager.delOrderMsg', { id: o.id.slice(0, 8) }),
    confirmText: t('manager.delOrderYes'),
    danger: true,
  })
  if (!ok) return
  try { await ordersStore.hide(o.id); toast.show(t('manager.orderDeleted')) }
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
/* the whole card opens the details dialog */
.o-card { cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.o-card:hover { border-color: rgba(60,74,39,.35); box-shadow: 0 10px 24px -18px rgba(60,74,39,.9); }
.o-card:focus-visible { outline: 2px solid var(--green); outline-offset: 2px; }
/* details dialog */
.d-head { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; justify-content: center; margin-bottom: .4rem; }
.d-sec { font-size: .82rem; font-weight: 700; color: var(--green); margin: .9rem 0 .35rem; }
.d-box { background: var(--paper, #fff); border: 1px solid rgba(60,74,39,.12); border-radius: 12px; padding: .7rem .85rem; }
.d-name { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-weight: 700; color: var(--green); }
.d-phone { font-family: monospace; font-size: 1.15rem; color: var(--terra-deep, var(--green)); margin-top: .2rem; }
.d-note { margin-top: .3rem; color: var(--muted); font-size: .88rem; }
.d-actions { display: flex; gap: .45rem; flex-wrap: wrap; margin-top: .6rem; }
.d-act {
  padding: .4rem .85rem; border-radius: 999px; font-size: .85rem; font-weight: 600;
  border: 1.5px solid rgba(60,74,39,.25); color: var(--green); background: transparent;
  cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: .3rem;
}
.d-act:hover { background: var(--green); color: #fff; border-color: var(--green); }
/* WhatsApp is the fastest way to reach a customer here — make it the loud one */
.d-act.wa { background: #25d366; border-color: #25d366; color: #fff; }
.d-act.wa:hover { background: #1da851; border-color: #1da851; }
.d-line { font-size: .88rem; padding: .12rem 0; }
.d-sum { border-top: 1px solid rgba(60,74,39,.1); margin-top: .35rem; padding-top: .35rem; }
.d-total { border-top: 1px solid rgba(60,74,39,.15); margin-top: .35rem; padding-top: .35rem; font-weight: 700; color: var(--green); }
.d-time { list-style: none; margin: 0; padding: 0; }
.d-time li { display: flex; justify-content: space-between; gap: .6rem; font-size: .85rem; padding: .25rem 0; border-inline-start: 2px solid rgba(60,74,39,.15); padding-inline-start: .7rem; }
.o-del {
  flex: 0 0 auto; width: 34px; height: 34px; border-radius: 9px;
  display: grid; place-items: center; cursor: pointer;
  background: transparent; border: 1.5px solid rgba(178,59,59,.35); color: var(--red, #b23b3b);
  transition: background .15s, color .15s;
}
.o-del:hover { background: var(--red, #b23b3b); color: #fff; }
.o-del svg { width: 17px; height: 17px; }
/* on phones, stack the card: info on top, then total + status on their own row */
@media (max-width: 560px) {
  .order-top { flex-direction: column; align-items: stretch; gap: .6rem; }
  .order-ctrls { width: 100%; justify-content: space-between; }
  .order-ctrls .a-status { flex: 1 1 auto; min-width: 0; }
}
</style>
