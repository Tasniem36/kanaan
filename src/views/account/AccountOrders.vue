<template>
  <section class="panel">
    <div class="panel-head"><h2>{{ t('account.orders') }}</h2></div>
    <p v-if="ordersStore.loading" class="a-muted">{{ t('common.loading') }}</p>
    <p v-else-if="!ordersStore.orders.length" class="a-muted">{{ t('account.noOrders') }} <RouterLink to="/" style="color:var(--green);text-decoration:underline">{{ t('account.shopNow') }}</RouterLink></p>
    <div v-else class="a-card" v-for="o in ordersStore.orders" :key="o.id">
      <div class="a-row">
        <div>
          <span style="font-family:monospace;color:var(--green)">#{{ o.id.slice(0, 8) }}</span>
          <span class="a-muted"> · {{ fmtDate(o.created_at) }}</span>
        </div>
        <div class="a-row" style="gap:.6rem">
          <span class="a-total">{{ o.total }} <span class='dh' role='img' aria-label='درهم'></span></span>
          <span class="a-pill" :class="statusClass(o.status)">{{ statusLabel(o.status) }}</span>
        </div>
      </div>
      <div style="margin-top:.4rem;border-top:1px solid rgba(60,74,39,.1);padding-top:.4rem">
        <div class="a-row" v-for="(it, ix) in o.items" :key="ix" style="font-size:.88rem;padding:.1rem 0">
          <span>{{ it.name }} × {{ it.qty }}</span><span class="a-muted">{{ it.price * it.qty }} <span class='dh' role='img' aria-label='درهم'></span></span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../../stores/orders'

const { t, locale } = useI18n()
const ordersStore = useOrdersStore()

const statusLabel = (s) => t(`status.${s}`)
const statusClass = (s) => ({ pending: 'pill-warn', paid: 'pill-ok', fulfilled: 'pill-ok', cancelled: 'pill-low' }[s] || '')
const fmtDate = (d) => new Date(d).toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })

onMounted(() => ordersStore.fetch())
</script>

<style scoped>
.panel { background: #fff; border-radius: 18px; padding: 1.4rem; margin-top: 1.4rem; box-shadow: 0 8px 30px rgba(60,74,39,.06); }
.panel-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.35rem; margin-bottom: .8rem; }
</style>
