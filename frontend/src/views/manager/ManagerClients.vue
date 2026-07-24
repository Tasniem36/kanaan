<template>
  <section>
    <h1>{{ t('manager.clientsTitle') }}</h1>
    <p v-if="loading" class="a-muted">{{ t('common.loading') }}</p>
    <p v-else-if="!clients.length" class="a-muted">{{ t('manager.noClients') }}</p>
    <div v-else class="table-wrap">
      <table class="a-table">
        <thead><tr><th>{{ t('manager.colClient') }}</th><th>{{ t('manager.colPhone') }}</th><th>{{ t('manager.colOrders') }}</th><th>{{ t('manager.colSpent') }}</th><th>{{ t('manager.colLast') }}</th></tr></thead>
        <tbody>
          <tr v-for="c in clients" :key="c.id">
            <td><b style="color:var(--green)">{{ c.full_name || '—' }}</b><br><span class="a-muted" dir="ltr">{{ c.email }}</span></td>
            <td dir="ltr">{{ c.phone || '—' }}</td>
            <td>{{ c.orders_count }}</td>
            <td>{{ c.total_spent }} <span class='dh' role='img' aria-label='درهم'></span></td>
            <td class="a-muted">{{ c.last_order_at ? fmtDate(c.last_order_at) : t('manager.none') }}</td>
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

const { t, locale } = useI18n()
const clients = ref([])
const loading = ref(false)

const fmtDate = (d) => new Date(d).toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })

onMounted(async () => {
  loading.value = true
  try { const { clients: c } = await api('/users/clients'); clients.value = c }
  finally { loading.value = false }
})
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
</style>
