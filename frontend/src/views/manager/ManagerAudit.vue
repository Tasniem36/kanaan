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
    <Loader v-if="loading" :label="t('common.loading')" />
    <p v-else-if="!visibleLogs.length" class="a-muted">{{ t('manager.noAudit') }}</p>
    <div v-else class="table-wrap">
      <table class="a-table">
        <thead><tr><th>{{ t('manager.colWhen') }}</th><th>{{ t('manager.colWho') }}</th><th>{{ t('manager.colEmail') }}</th><th>{{ t('manager.colRole') }}</th><th>{{ t('manager.colAction') }}</th><th>{{ t('manager.colDetail') }}</th><th>{{ t('manager.colPage') }}</th><th>{{ t('manager.colLocation') }}</th><th>IP</th></tr></thead>
        <tbody>
          <tr v-for="a in visibleLogs" :key="a.id">
            <td class="a-muted" style="white-space:nowrap">{{ fmtDateTime(a.created_at) }}</td>
            <td><b v-if="a.email" style="color:var(--green)">{{ a.full_name || '—' }}</b><span v-else class="a-muted">{{ t('manager.guestVisitor') }}</span></td>
            <td class="a-muted" dir="ltr" style="font-size:.85rem">{{ a.email || '—' }}</td>
            <td><span class="a-pill" :class="roleClass(a)">{{ roleLabel(a) }}</span></td>
            <td><span class="a-pill" :class="pillClass(a.action)">{{ actionLabel(a.action) }}</span></td>
            <td class="a-muted" style="font-size:.85rem">{{ detailText(a) }}</td>
            <td class="page-cell"><a v-if="a.page" href="#" class="page-link" dir="ltr" @click.prevent="goPage(a.page)">{{ a.page }}</a><span v-else class="a-muted">—</span></td>
            <td class="a-muted" style="font-size:.82rem">{{ geo[a.ip] || '—' }}</td>
            <td class="a-muted" dir="ltr" style="font-size:.8rem">{{ a.ip || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'
import { EMIRATES } from '../../utils/delivery'
import Loader from '../../components/Loader.vue'

const { t, te, locale } = useI18n()
const router = useRouter()
const logs = ref([])
const geo = ref({})   // ip → "City, Country" (filled in after the rows load)
const loading = ref(false)
const filters = reactive({ email: '', action: '', from: '', to: '', location: '' })
const actionOptions = ['login', 'register', 'order_placed', 'payment_confirmed', 'address_added', 'address_removed', 'visit']

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

function goPage(p) { try { router.push(p) } catch { /* not an in-app route */ } }

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
  if (action === 'visit') return ''
  return 'pill-ok'
}

function detailText(a) {
  const d = a.detail || {}
  if (a.action === 'order_placed')
    return `#${String(d.order_id || '').slice(0, 8)} · ${d.total}` + (d.discount_code ? ` · ${d.discount_code}` : '') + (d.payment_method ? ` · ${d.payment_method}` : '')
  if (a.action === 'payment_confirmed') return `#${String(d.order_id || '').slice(0, 8)} · ${d.total}`
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
    loadGeo(rows)
  } finally {
    loading.value = false
  }
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
  debTimer = setTimeout(load, 350)
})

function clearFilter() {
  Object.assign(filters, { email: '', action: '', from: '', to: '', location: '' })
  load()
}
onMounted(load)
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.a-pill { font-size: .78rem; }
.filters { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin-bottom: 1rem; }
.filters .a-input, .filters .a-select { max-width: 180px; }
.a-btn.ghost { background: var(--cream-2); color: var(--green); }
/* keep the page column from stretching the table — wrap long paths instead */
.page-cell { max-width: 200px; }
.page-link { color: var(--green); text-decoration: underline; cursor: pointer; word-break: break-all; font-size: .8rem; }
.page-link:hover { color: var(--gold); }
</style>
