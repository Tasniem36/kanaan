<template>
  <section>
    <h1>{{ t('manager.allOrders') }}</h1>
    <p v-if="ordersStore.loading" class="a-muted">{{ t('common.loading') }}</p>
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('manager.noOrders') }}</p>
    <div class="a-card" v-for="o in ordersStore.orders" :key="o.id">
      <div class="a-row">
        <div>
          <div><span style="font-family:monospace;color:var(--green)">#{{ o.id.slice(0, 8) }}</span> <span class="a-muted">· {{ fmtDate(o.created_at) }}</span></div>
          <div class="a-muted" style="margin-top:.15rem"><b style="color:var(--ink)">{{ o.customer_name }}</b> · ☎ <span dir="ltr">{{ o.phone }}</span></div>
          <div class="a-muted">📍 {{ o.city }}، {{ o.street }}، منزل {{ o.house }}<span v-if="o.notes"> ({{ o.notes }})</span></div>
        </div>
        <div class="a-row" style="gap:.6rem">
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
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'
import { useToastStore } from '../../stores/toast'

const { t, locale } = useI18n()
const ordersStore = useOrdersStore()
const toast = useToastStore()

const fmtDate = (d) => new Date(d).toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })

async function changeStatus(o, status) {
  try { await ordersStore.setStatus(o.id, status); toast.show(t('manager.toastStatus')) }
  catch (e) { toast.show(e.message) }
}

onMounted(() => ordersStore.fetch())
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
</style>
