<template>
  <div class="pay-wrap">
    <div class="pay-card">
      <template v-if="state === 'verifying'">
        <div class="spinner" aria-hidden="true"></div>
        <p class="muted">{{ t('pay.verifying') }}</p>
      </template>

      <template v-else-if="state === 'success'">
        <div class="pay-ic ok" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>
        </div>
        <h1>{{ t('pay.success') }}</h1>
        <p class="muted">{{ t('pay.successMsg', { id: shortId }) }}</p>
        <RouterLink to="/" class="btn btn-green">{{ t('pay.backHome') }}</RouterLink>
      </template>

      <template v-else>
        <div class="pay-ic fail" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6 6 18"/></svg>
        </div>
        <h1>{{ t('pay.failed') }}</h1>
        <p class="muted">{{ t('pay.failedMsg') }}</p>
        <RouterLink to="/" class="btn btn-green">{{ t('pay.backHome') }}</RouterLink>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useOrdersStore } from '../stores/orders'

const { t } = useI18n()
const route = useRoute()
const ordersStore = useOrdersStore()

const state = ref('verifying') // verifying | success | failed
const orderId = String(route.query.order || '')
const shortId = computed(() => orderId.slice(0, 8))

onMounted(async () => {
  if (!orderId || route.query.cancel) { state.value = 'failed'; return }
  // Ziina may take a moment to mark the intent completed — retry a few times.
  for (let i = 0; i < 3; i++) {
    try {
      const r = await ordersStore.confirmPayment(orderId)
      if (r.paid) { state.value = 'success'; return }
    } catch { /* keep trying */ }
    await new Promise((res) => setTimeout(res, 1500))
  }
  state.value = 'failed'
})
</script>

<style scoped>
.pay-wrap { min-height: 100vh; display: grid; place-items: center; padding: 2rem 1rem; background: var(--cream, #f5efe3); }
.pay-card { width: 100%; max-width: 420px; background: #fff; border-radius: 20px; padding: 2.4rem 2rem; text-align: center; box-shadow: 0 20px 60px rgba(60,74,39,.12); }
.pay-card h1 { font-family: 'Amiri', serif; color: var(--green, #3c4a27); font-size: 1.6rem; margin: 0.4rem 0; }
.muted { color: var(--muted, #8a7f64); font-size: 0.95rem; margin-bottom: 1.2rem; }
.pay-ic { width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center; margin: 0 auto 0.6rem; }
.pay-ic svg { width: 34px; height: 34px; }
.pay-ic.ok { background: rgba(60,74,39,.12); color: var(--green, #3c4a27); }
.pay-ic.fail { background: rgba(156,43,43,.12); color: var(--red, #9c2b2b); }
.spinner { width: 44px; height: 44px; border: 4px solid rgba(60,74,39,.15); border-top-color: var(--green, #3c4a27); border-radius: 50%; margin: 0 auto 1rem; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.btn { display: inline-flex; align-items: center; justify-content: center; padding: 0.75rem 1.6rem; border-radius: 999px; font-weight: 700; }
.btn-green { background: var(--green, #3c4a27); color: #fff; }
</style>
