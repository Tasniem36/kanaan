<template>
  <section>
    <h1>{{ t('manager.auditTitle') }}</h1>
    <p v-if="loading" class="a-muted">{{ t('common.loading') }}</p>
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
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'

const { t, te, locale } = useI18n()
const logs = ref([])
const loading = ref(false)

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

onMounted(async () => {
  loading.value = true
  try {
    const { logs: rows } = await api('/audit')
    logs.value = rows
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.a-pill { font-size: .78rem; }
</style>
