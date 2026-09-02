<template>
  <!-- basket sidebar (slides in from the side) -->
  <transition name="v"><div v-if="open" class="overlay" @click="emit('close')"></div></transition>
  <aside class="drawer" :class="{ open }" aria-label="سلّة المشتريات">
    <div class="drawer-head">
      <b>{{ t('cart.title') }}</b>
      <button class="close" @click="emit('close')" :aria-label="t('cart.title')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>
      </button>
    </div>
    <div class="drawer-body">
      <div v-if="!cart.list.length" class="empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
        <b>{{ t('cart.empty') }}</b>{{ t('cart.emptySub') }}
        <div style="margin-top:1.2rem"><a href="#shop" class="btn btn-green" @click="emit('close')">{{ t('cart.browse') }}</a></div>
      </div>
      <div v-else>
        <div class="cart-item" v-for="it in cart.list" :key="it.id">
          <span class="pic"><img :src="it.image_url" :alt="pName(it)"></span>
          <div class="info">
            <h4>{{ pName(it) }}</h4>
            <div class="u">{{ ar(pPrice(it)) }} <span class='dh' role='img' aria-label='درهم'></span> <s v-if="pIsOnSale(it)" class="was">{{ ar(it.price) }}</s> × {{ ar(it.q) }}</div>
            <button class="remove" @click="cart.removeAll(it.id)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14" stroke-linecap="round"><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13"/></svg>{{ t('cart.remove') }}
            </button>
          </div>
          <span class="mini-step">
            <button @click="cart.dec(it.id)" aria-label="إنقاص">−</button>
            <span>{{ ar(it.q) }}</span>
            <button @click="cart.add(it)" aria-label="زيادة">+</button>
          </span>
        </div>
      </div>
    </div>
    <div class="drawer-foot" v-if="cart.list.length">
      <!-- free-delivery progress nudge (threshold set by the admin) -->
      <div v-if="freeThreshold > 0" class="free-bar" :class="{ done: cart.total >= freeThreshold }">
        <p class="free-msg">{{ cart.total >= freeThreshold ? t('cart.freeNoteQualified') : t('cart.freeNoteAdd', { amount: ar(remaining) }) }}</p>
        <div class="free-track"><span class="free-fill" :style="{ width: pct + '%' }"></span></div>
      </div>
      <div class="totals"><span class="lbl">{{ t('cart.total') }}</span><span class="amt">{{ ar(cart.total) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
      <button class="checkout" @click="emit('checkout')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>{{ t('cart.checkout') }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'
import { useSettingsStore } from '../stores/settings'
import { pName, pPrice, pIsOnSale } from '../utils/product'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'checkout'])

const { t } = useI18n()
const cart = useCartStore()
const settings = useSettingsStore()
const ar = (n) => String(n)
const freeThreshold = computed(() => Number(settings.delivery?.free_threshold) || 0)
const remaining = computed(() => Math.max(0, freeThreshold.value - cart.total))
const pct = computed(() => (freeThreshold.value > 0 ? Math.min(100, Math.round((cart.total / freeThreshold.value) * 100)) : 0))

// Load the admin's delivery config the first time the cart opens, so the free
// threshold is correct on every page (not only the home page, which fetched it).
let loaded = false
watch(() => props.open, (o) => { if (o && !loaded) { loaded = true; settings.fetchDelivery() } })
</script>

<style scoped>
.u .was { color: var(--muted, #8a7f64); opacity: .8; margin-inline: .25rem; }
.free-bar {
  margin-bottom: .9rem; padding: .6rem .8rem; border-radius: 12px;
  background: var(--cream-2, rgba(60,74,39,.08)); border: 1px solid rgba(184,144,47,.35);
}
.free-bar.done { border-color: var(--green, #3c4a27); background: rgba(60,74,39,.09); }
.free-msg { font-size: .85rem; font-weight: 700; color: var(--green, #3c4a27); margin: 0 0 .45rem; line-height: 1.4; }
.free-track { height: 7px; border-radius: 999px; background: rgba(60,74,39,.15); overflow: hidden; }
.free-fill { display: block; height: 100%; border-radius: 999px; background: var(--gold, #b8902f); transition: width .4s ease; }
.free-bar.done .free-fill { background: var(--green, #3c4a27); }
</style>
