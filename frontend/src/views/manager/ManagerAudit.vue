<template>
  <section>
    <h1>{{ t('manager.auditTitle') }}</h1>
    <div class="filters">
      <input class="a-input" v-model.trim="filters.email" :placeholder="t('manager.colEmail')" dir="ltr">
      <select class="a-select" v-model="filters.action">
        <option value="">{{ t('manager.allActions') }}</option>
        <option v-for="a in actionOptions" :key="a" :value="a">{{ actionLabel(a) }}</option>
      </select>
      <select class="a-select" v-model="filters.location">
        <option value="">{{ t('manager.allLocations') }}</option>
        <option v-for="e in EMIRATES" :key="e.value" :value="e.value">{{ locale === 'ar' ? e.value : e.en }}</option>
      </select>
      <input class="a-input" type="date" v-model="filters.from" :title="t('manager.from')">
      <input class="a-input" type="date" v-model="filters.to" :title="t('manager.to')">
      <button class="a-btn ghost" @click="clearFilter">{{ t('manager.clearFilter') }}</button>
    </div>

    <!-- Most-opened products (from the product_view trail; honours the date range) -->
    <div v-if="topProducts.length" class="top-products">
      <h2>{{ t('manager.topProducts') }}</h2>
      <ol class="top-list">
        <li v-for="p in topProducts" :key="p.product_id">
          <a :href="`/product/${p.product_id}`" target="_blank" rel="noopener" class="top-name">{{ p.name || p.product_id }}</a>
          <span class="top-count">{{ t('manager.viewsCount', { n: p.views }) }}</span>
        </li>
      </ol>
    </div>

    <Loader v-if="loading" :label="t('common.loading')" />
    <p v-else-if="!visibleLogs.length" class="a-muted">{{ t('manager.noAudit') }}</p>
    <div v-else class="table-wrap">
      <table class="a-table">
        <thead><tr><th>{{ t('manager.colWhen') }}</th><th>{{ t('manager.colWho') }}</th><th>{{ t('manager.colEmail') }}</th><th>{{ t('manager.colRole') }}</th><th>{{ t('manager.colAction') }}</th><th>{{ t('manager.colDetail') }}</th><th>{{ t('manager.colApi') }}</th><th>{{ t('manager.colLocation') }}</th><th>IP</th></tr></thead>
        <tbody>
          <tr v-for="a in pagedLogs" :key="a.id">
            <td class="a-muted" style="white-space:nowrap">{{ fmtDateTime(a.created_at) }}</td>
            <td><b v-if="a.email" style="color:var(--green)">{{ a.full_name || '—' }}</b><span v-else class="a-muted">{{ t('manager.guestVisitor') }}</span></td>
            <td class="a-muted" dir="ltr" style="font-size:.85rem">{{ a.email || '—' }}</td>
            <td><span class="a-pill" :class="roleClass(a)">{{ roleLabel(a) }}</span></td>
            <td><span class="a-pill" :class="pillClass(a.action)">{{ actionLabel(a.action) }}</span></td>
            <td class="a-muted" style="font-size:.85rem">{{ detailText(a) }}</td>
            <!-- the endpoint the action went through; the page it came from is on
                 hover, since that's context rather than the action itself -->
            <td class="page-cell">
              <code v-if="a.api" class="api" dir="ltr" :title="a.page || ''">{{ a.api }}</code>
              <span v-else class="a-muted">—</span>
            </td>
            <td class="a-muted" style="font-size:.82rem">{{ geo[a.ip] || '—' }}</td>
            <td class="a-muted" dir="ltr" style="font-size:.8rem">{{ a.ip || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- numbered pagination -->
      <nav v-if="pageCount > 1" class="pager" :aria-label="t('manager.pagination')">
        <button class="pg" :disabled="page === 1" @click="go(page - 1)" :aria-label="t('manager.prevPage')">‹</button>
        <template v-for="(p, i) in pageNumbers" :key="i">
          <span v-if="p === '…'" class="pg-gap">…</span>
          <button v-else class="pg" :class="{ on: p === page }" @click="go(p)">{{ p }}</button>
        </template>
        <button class="pg" :disabled="page === pageCount" @click="go(page + 1)" :aria-label="t('manager.nextPage')">›</button>
      </nav>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'
import { EMIRATES } from '../../utils/delivery'
import Loader from '../../components/Loader.vue'

const { t, te, locale } = useI18n()
const logs = ref([])
const topProducts = ref([])
const geo = ref({})   // ip → "City, Country" (filled in after the rows load)
const loading = ref(false)
const filters = reactive({ email: '', action: '', from: '', to: '', location: '' })
const actionOptions = ['login', 'register', 'order_placed', 'payment_confirmed', 'address_added', 'address_removed', 'product_view', 'visit']

const PAGE_SIZE = 30
const page = ref(1)

// location filter is applied client-side against the resolved geo (city/country)
const visibleLogs = computed(() => {
  if (!filters.location) return logs.value
  const em = EMIRATES.find((e) => e.value === filters.location)
  const needles = [filters.location, em && em.en].filter(Boolean).map((s) => s.toLowerCase())
  return logs.value.filter((a) => {
    const loc = (geo.value[a.ip] || '').toLowerCase()
    return needles.some((n) => loc.includes(n))
  })
})

const pageCount = computed(() => Math.max(1, Math.ceil(visibleLogs.value.length / PAGE_SIZE)))
const pagedLogs = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return visibleLogs.value.slice(start, start + PAGE_SIZE)
})
// windowed page numbers: 1 … (p-1) p (p+1) … last
const pageNumbers = computed(() => {
  const last = pageCount.value
  const cur = page.value
  const set = new Set([1, last, cur, cur - 1, cur + 1])
  const nums = [...set].filter((n) => n >= 1 && n <= last).sort((a, b) => a - b)
  const out = []
  let prev = 0
  for (const n of nums) {
    if (n - prev > 1) out.push('…')
    out.push(n)
    prev = n
  }
  return out
})
function go(p) {
  page.value = Math.min(Math.max(1, p), pageCount.value)
}
// reset to the first page whenever the visible set changes underneath us
watch(visibleLogs, () => { if (page.value > pageCount.value) page.value = pageCount.value })

// A product_view row links straight to the product it recorded; everything else
// links to the page the action came from. Opens in a new tab so the manager
// never loses their place in the log.

const fmtDateTime = (d) =>
  new Date(d).toLocaleString(locale.value, { dateStyle: 'medium', timeStyle: 'short' })

const actionLabel = (a) => (te(`audit.${a}`) ? t(`audit.${a}`) : a)

function roleLabel(a) {
  if (!a.email) return t('manager.guestVisitor')
  return a.role === 'manager' ? t('manager.roleAdmin') : t('manager.roleCustomer')
}
function roleClass(a) {
  if (!a.email) return ''
  return a.role === 'manager' ? 'pill-warn' : 'pill-ok'
}

function pillClass(action) {
  if (action === 'payment_confirmed') return 'pill-ok'
  if (action === 'order_placed') return 'pill-warn'
  if (action === 'visit' || action === 'product_view') return ''
  return 'pill-ok'
}

function detailText(a) {
  const d = a.detail || {}
  if (a.action === 'order_placed')
    return `#${String(d.order_id || '').slice(0, 8)} · ${d.total}` + (d.discount_code ? ` · ${d.discount_code}` : '') + (d.payment_method ? ` · ${d.payment_method}` : '')
  if (a.action === 'payment_confirmed') return `#${String(d.order_id || '').slice(0, 8)} · ${d.total}`
  if (a.action === 'product_view') return d.name || ''
  if (a.action === 'address_added') return d.city || ''
  return ''
}

async function load() {
  loading.value = true
  try {
    const qs = new URLSearchParams()
    if (filters.email) qs.set('email', filters.email)
    if (filters.action) qs.set('action', filters.action)
    if (filters.from) qs.set('from', filters.from)
    if (filters.to) qs.set('to', filters.to)
    const { logs: rows } = await api('/audit' + (qs.toString() ? `?${qs}` : ''))
    logs.value = rows
    page.value = 1
    loadGeo(rows)
  } finally {
    loading.value = false
  }
}

// the "most opened products" panel — respects only the date range (not the
// action/email filters, which don't apply to a product ranking)
async function loadTopProducts() {
  const qs = new URLSearchParams()
  if (filters.from) qs.set('from', filters.from)
  if (filters.to) qs.set('to', filters.to)
  try {
    const { products } = await api('/audit/top-products' + (qs.toString() ? `?${qs}` : ''))
    topProducts.value = products || []
  } catch { topProducts.value = [] }
}

// resolve the distinct IPs on this page to locations (best-effort, non-blocking)
async function loadGeo(rows) {
  const ips = [...new Set(rows.map((r) => r.ip).filter((ip) => ip && !(ip in geo.value)))]
  if (!ips.length) return
  try {
    const { geo: found } = await api(`/audit/geo?ips=${encodeURIComponent(ips.join(','))}`)
    geo.value = { ...geo.value, ...found }
  } catch { /* leave IPs unresolved */ }
}
// server-side filters (email/action/dates) reload automatically on change (debounced,
// so typing an email doesn't hammer the API); the location filter is client-side.
let debTimer
watch(() => [filters.email, filters.action, filters.from, filters.to], () => {
  clearTimeout(debTimer)
  debTimer = setTimeout(() => { load(); loadTopProducts() }, 350)
})

function clearFilter() {
  Object.assign(filters, { email: '', action: '', from: '', to: '', location: '' })
  load()
  loadTopProducts()
}
onMounted(() => { load(); loadTopProducts() })
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.a-pill { font-size: .78rem; }
.filters { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin-bottom: 1rem; }
.filters .a-input, .filters .a-select { max-width: 180px; }
.a-btn.ghost { background: var(--cream-2); color: var(--green); }

/* most-opened products */
.top-products {
  background: var(--cream-2); border: 1px solid rgba(60, 74, 39, .12);
  border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 1.2rem;
}
.top-products h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.15rem; margin: 0 0 .6rem; }
.top-list { margin: 0; padding-inline-start: 1.4rem; display: grid; gap: .35rem; }
.top-list li { display: flex; justify-content: space-between; gap: .8rem; align-items: baseline; }
.top-name { color: var(--green); text-decoration: underline; font-weight: 600; }
.top-name:hover { color: var(--gold); }
.top-count { color: var(--muted); font-size: .85rem; white-space: nowrap; }

/* keep the endpoint column compact: one line, truncated with … */
.page-cell { max-width: 210px; }
.api {
  display: inline-block; max-width: 210px; vertical-align: bottom;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-size: .76rem; color: var(--green-2);
  background: rgba(60,74,39,.07); border-radius: 6px; padding: .1rem .4rem;
}
.page-link {
  display: inline-block; max-width: 200px; vertical-align: bottom;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--green); text-decoration: underline; cursor: pointer; font-size: .8rem;
}
.page-link:hover { color: var(--gold); }

/* numbered pagination */
.pager { display: flex; gap: .35rem; flex-wrap: wrap; align-items: center; justify-content: center; margin-top: 1.2rem; }
.pg {
  min-width: 36px; height: 36px; padding: 0 .5rem; border-radius: 9px;
  border: 1px solid rgba(60, 74, 39, .18); background: var(--cream);
  color: var(--green); font-family: inherit; font-weight: 600; cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
}
.pg:hover:not(:disabled) { border-color: var(--green); }
.pg.on { background: var(--green); color: var(--cream); border-color: var(--green); }
.pg:disabled { opacity: .4; cursor: default; }
.pg-gap { color: var(--muted); padding: 0 .2rem; }
</style>
