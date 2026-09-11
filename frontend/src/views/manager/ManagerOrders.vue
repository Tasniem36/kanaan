<template>
  <section>
    <div class="orders-head">
      <h1>{{ t('manager.allOrders') }}</h1>
      <!-- A customer rings quoting DK-EPBV9SH. Without this the till had no field to
           type it into: the tabs page ten customers at a time, so the only way to
           find the order was to scroll for it. -->
      <div class="psearch">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input class="a-input" v-model="q" :placeholder="t('manager.searchOrders')" :aria-label="t('manager.searchOrders')">
        <button v-if="q" class="pclear" :aria-label="t('search.clear')" @click="q = ''">×</button>
      </div>
    </div>
    <Loader v-if="ordersStore.loading && !ordersStore.orders.length" :label="t('common.loading')" />
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('manager.noOrders') }}</p>

    <template v-else>
      <!-- The tabs step aside while a search is running rather than narrowing it: a
           manager holding a number can't be expected to know which tab the order is
           sitting in, and a highlighted «الجديدة» above a delivered order is a lie. -->
      <template v-if="!searching">
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
      </template>
      <p v-else class="search-note a-muted">{{ t('manager.searchAllTabs', { n: matchCount }) }}</p>

      <p v-if="!visibleGroups.length" class="a-muted">
        {{ searching ? t('manager.searchNoOrders') : t('manager.noOrdersFilter') }}
      </p>
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
            <div><span style="font-family:monospace;color:var(--green)" dir="ltr">{{ orderNumber(o) }}</span> <span class="a-muted">· {{ fmtDate(o.created_at) }}</span></div>
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
          <span style="font-family:monospace;color:var(--green)" dir="ltr">{{ orderNumber(detail) }}</span>
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
import { dateTime } from '../../utils/datetime'
// The till calls an order what its customer calls it. This page used to print the
// first eight characters of the internal id, so a customer reading DK-EPBV9SH down
// the phone was quoting a number the shop had never seen — and the WhatsApp the
// manager sends back quoted one the customer had never seen.
import { orderNumber } from '../../utils/order'
import { foldArabic } from '../../utils/text'

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
    id: orderNumber(o),
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
const q = ref('')
const searching = computed(() => q.value.trim().length > 0)

const matchesPay = (o) => payFilter.value === 'all' || o.payment_method === payFilter.value
const tabStatuses = computed(() => STATUS_TABS.find((tb) => tb.key === activeTab.value)?.statuses || [])

// The number as a manager types it, against the number as the shop stores it: DK-, a
// leading #, spaces and case are all noise on something read down a phone line.
const bareRef = (s) => String(s || '').toUpperCase().replace(/[\s#]/g, '').replace(/^DK-/, '')
const digitsOf = (s) => String(s || '').replace(/\D/g, '')
// 0501234567, 501234567, +971501234567 and 00971501234567 are one phone number, and
// the shop holds a mix: checkout normalises to +971…, older rows still carry the
// local 05… form (the same spread waDigits below has to cope with). Comparing raw
// digits matched neither way round — a manager typing the number the customer just
// read out found nothing — so the country code and the trunk 0 come off both sides.
const localDigits = (s) => digitsOf(s).replace(/^00/, '').replace(/^971/, '').replace(/^0+/, '')
// Only a query that is all digits and phone punctuation is treated as a phone.
// Otherwise "DK-7DF2MCP" reduces to "72" and matches numbers at random.
const IS_PHONE = /^[\d\s+()-]+$/

function matchesQuery(o) {
  const raw = q.value.trim()
  if (!raw) return true
  const needle = bareRef(raw)
  if (needle && bareRef(orderNumber(o)).includes(needle)) return true
  const dialled = localDigits(raw)
  // 4 digits: enough to be the tail of a number somebody read out, short enough to
  // still be typed from memory
  if (IS_PHONE.test(raw) && dialled.length >= 4 && localDigits(o.phone).includes(dialled)) return true
  const name = foldArabic(raw)
  return !!name && foldArabic(o.customer_name).includes(name)
}

// A search reaches across every tab and both payment filters; without one, the tab
// and the filter decide. The two are never applied at once — see the template.
const shown = (o) => (searching.value
  ? matchesQuery(o)
  : tabStatuses.value.includes(o.status) && matchesPay(o))

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
    if (!shown(o)) continue
    const key = o.user_id || o.phone || o.id
    if (!map.has(key)) map.set(key, { key, name: o.customer_name, phone: o.phone, orders: [], total: 0 })
    const g = map.get(key)
    g.orders.push(o)
    g.total += Number(o.total)
  }
  return [...map.values()]
})

// orders, not customers — a search for one number that lands in a group of six
// should say it found one
const matchCount = computed(() => groups.value.reduce((n, g) => n + g.orders.length, 0))

const { visible: visibleGroups, sentinel, hasMore, reset } = useInfiniteScroll(() => groups.value, 10)
// restart paging from the top whenever the tab, payment filter or search changes —
// otherwise a search starts halfway down someone else's scroll position
watch([activeTab, payFilter, q], reset)

// date + time of the order, in the manager's local timezone
const fmtDate = (d) => dateTime(d, locale.value)

async function changeStatus(o, e) {
  const status = e.target.value
  if (status === o.status) return
  const ok = await confirm.ask({
    title: t('manager.statusConfirmTitle'),
    message: t('manager.statusConfirmMsg', { id: orderNumber(o), status: t(`status.${status}`) }),
    confirmText: t('manager.statusConfirmYes'),
  })
  if (!ok) { e.target.value = o.status; return }   // reverted → put the dropdown back
  try { await ordersStore.setStatus(o.id, status); toast.show(t('manager.toastStatus')) }
  catch (err) { toast.show(err.message); e.target.value = o.status }
}

async function deleteOrder(o) {
  const ok = await confirm.ask({
    title: t('manager.delOrderTitle'),
    message: t('manager.delOrderMsg', { id: orderNumber(o) }),
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
/* the same search box as the products page, so the two manager screens don't each
   have their own idea of what one looks like */
.psearch { position: relative; flex: 1 1 210px; max-width: 320px; display: flex; align-items: center; }
.psearch svg { position: absolute; inset-inline-start: .6rem; width: 15px; height: 15px;
  fill: none; stroke: var(--muted, #8a7f64); stroke-width: 2; stroke-linecap: round; pointer-events: none; }
.psearch .a-input { width: 100%; padding-inline-start: 2rem; padding-inline-end: 1.8rem; font-size: .85rem; }
.pclear { position: absolute; inset-inline-end: .45rem; font-size: 1.1rem; line-height: 1;
  color: var(--muted, #8a7f64); background: none; border: 0; padding: .1rem .25rem; }
.search-note { font-size: .84rem; margin-bottom: .8rem; }
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
