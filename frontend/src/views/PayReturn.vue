<template>
  <div class="pay-wrap">
    <div class="pay-card">
      <template v-if="state === 'verifying'">
        <div class="spinner" aria-hidden="true"></div>
        <p class="muted">{{ t('pay.verifying') }}</p>
        <p class="keep-open">{{ t('pay.keepOpen') }}</p>
      </template>

      <template v-else-if="state === 'success'">
        <div class="pay-ic ok" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>
        </div>
        <h1>{{ t('pay.success') }}</h1>
        <p class="muted">{{ t('pay.successMsg', { id: shortId }) }}</p>
        <RouterLink to="/" class="btn btn-green">{{ t('pay.backHome') }}</RouterLink>
      </template>

      <!-- No answer either way. Deliberately not the failure screen: "try again" to
           someone whose payment is still going through buys the same basket twice. -->
      <template v-else-if="state === 'unresolved'">
        <div class="pay-ic wait" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
        </div>
        <h1>{{ t('pay.unresolved') }}</h1>
        <p class="muted">{{ t('pay.unresolvedMsg') }}</p>
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
import { useCartStore } from '../stores/cart'

const { t } = useI18n()
const route = useRoute()
const ordersStore = useOrdersStore()
const cart = useCartStore()

const state = ref('verifying') // verifying | success | unresolved | failed
const orderId = String(route.query.order || '')
// guests have no session here — the tracking token from the return URL is what
// authorises confirming/cancelling their own payment
const token = String(route.query.t || '')
const shortId = computed(() => orderId.slice(0, 8))

// The basket is emptied here, not before the redirect to Ziina — so a payment that
// was abandoned, refused, or simply backed out of leaves it intact to try again.
// Only money actually arriving clears it.
function settle() {
  state.value = 'success'
  cart.clear()
}

// Ziina can take a moment to mark an intent completed, and a card being authorised
// takes longer than a wallet. Long enough to cover that, short enough that nobody
// watches a spinner wondering — past this the answer isn't going to arrive while they
// wait, and reconcile.py settles the order whatever this page ends up showing.
const TRIES = 8
// Someone who meant to cancel is owed a quicker answer than someone waiting to be
// told they paid, and their intent will sit unresolved for as long as we poll it.
const CANCEL_TRIES = 3
const GAP_MS = 2000

onMounted(async () => {
  if (!orderId) { state.value = 'failed'; return }
  // cancel=1 says which URL Ziina redirected to, not what happened to the money — they
  // may have paid and then hit cancel or the back button. So the server checks the intent
  // before cancelling and answers paid if it completed; trusting the button over that
  // answer would show "payment failed", basket still full, to someone who has paid.
  let tries = TRIES
  if (route.query.cancel) {
    const r = await ordersStore.cancelPayment(orderId, token).catch(() => null)
    if (r?.paid) { settle(); return }
    // Not cancelled either: Ziina hadn't resolved the intent, or couldn't be asked. The
    // order is still alive and the money may still be arriving, so poll it out like any
    // other return rather than telling someone mid-payment that it failed.
    if (!r?.pending) { state.value = 'failed'; return }
    tries = CANCEL_TRIES
  }
  for (let i = 0; i < tries; i++) {
    try {
      const r = await ordersStore.confirmPayment(orderId, token)
      if (r.paid) { settle(); return }
      // Ziina said the money is not coming. That is an answer, and the only one that
      // earns the failure screen with its invitation to try again.
      if (r.status === 'failed') { state.value = 'failed'; return }
    } catch { /* keep trying */ }
    if (i < tries - 1) await new Promise((res) => setTimeout(res, GAP_MS))
  }
  state.value = 'unresolved'
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
.pay-ic.wait { background: rgba(180,134,44,.14); color: #b4862c; }
.keep-open { color: var(--muted, #8a7f64); font-size: 0.82rem; opacity: 0.85; }
.spinner { width: 44px; height: 44px; border: 4px solid rgba(60,74,39,.15); border-top-color: var(--green, #3c4a27); border-radius: 50%; margin: 0 auto 1rem; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.btn { display: inline-flex; align-items: center; justify-content: center; padding: 0.75rem 1.6rem; border-radius: 999px; font-weight: 700; }
.btn-green { background: var(--green, #3c4a27); color: #fff; }
</style>
