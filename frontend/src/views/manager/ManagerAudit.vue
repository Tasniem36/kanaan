<template>
  <section>
    <h1>{{ t('manager.auditTitle') }}</h1>
    <div class="filters">
      <input class="a-input" v-model.trim="filters.email" :placeholder="t('manager.colEmail')" dir="ltr" @keyup.enter="load">
      <select class="a-select" v-model="filters.action">
        <option value="">{{ t('manager.allActions') }}</option>
        <option v-for="a in actionOptions" :key="a" :value="a">{{ actionLabel(a) }}</option>
      </select>
      <input class="a-input" type="date" v-model="filters.from" :title="t('manager.from')">
      <input class="a-input" type="date" v-model="filters.to" :title="t('manager.to')">
      <button class="a-btn" @click="load">{{ t('manager.applyFilter') }}</button>
      <button class="a-btn ghost" @click="clearFilter">{{ t('manager.clearFilter') }}</button>
    </div>
    <Loader v-if="loading" :label="t('common.loading')" />
    <p v-else-if="!logs.length" class="a-muted">{{ t('manager.noAudit') }}</p>
    <div v-else class="table-wrap">
      <table class="a-table">
        <thead><tr><th>{{ t('manager.colWhen') }}</th><th>{{ t('manager.colWho') }}</th><th>{{ t('manager.colEmail') }}</th><th>{{ t('manager.colRole') }}</th><th>{{ t('manager.colAction') }}</th><th>{{ t('manager.colDetail') }}</th><th>IP</th></tr></thead>
        <tbody>
          <tr v-for="a in logs" :key="a.id">
            <td class="a-muted" style="white-space:nowrap">{{ fmtDateTime(a.created_at) }}</td>
            <td><b v-if="a.email" style="color:var(--green)">{{ a.full_name || '—' }}</b><span v-else class="a-muted">{{ t('manager.guestVisitor') }}</span></td>
            <td class="a-muted" dir="ltr" style="font-size:.85rem">{{ a.email || '—' }}</td>
            <td><span class="a-pill" :class="roleClass(a)">{{ roleLabel(a) }}</span></td>
            <td><span class="a-pill" :class="pillClass(a.action)">{{ actionLabel(a.action) }}</span></td>
            <td class="a-muted" style="font-size:.85rem">{{ detailText(a) }}</td>
            <td class="a-muted" dir="ltr" style="font-size:.8rem">{{ a.ip || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'
import Loader from '../../components/Loader.vue'

const { t, te, locale } = useI18n()
const logs = ref([])
const loading = ref(false)
const filters = reactive({ email: '', action: '', from: '', to: '' })
const actionOptions = ['login', 'register', 'order_placed', 'payment_confirmed', 'address_added', 'address_removed', 'visit']

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
  } finally {
    loading.value = false
  }
}
function clearFilter() {
  Object.assign(filters, { email: '', action: '', from: '', to: '' })
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
</style>
