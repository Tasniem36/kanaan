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
        <div style="margin-top:1.2rem"><a href="#pantry" class="btn btn-green" @click="emit('close')">{{ t('cart.browse') }}</a></div>
      </div>
      <div v-else>
        <div class="cart-item" v-for="it in cart.list" :key="it.id">
          <span class="pic"><img :src="it.image_url" :alt="it.name"></span>
          <div class="info">
            <h4>{{ it.name }}</h4>
            <div class="u">{{ ar(it.price) }} <span class='dh' role='img' aria-label='درهم'></span> × {{ ar(it.q) }}</div>
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
      <div class="totals"><span class="lbl">{{ t('cart.total') }}</span><span class="amt">{{ ar(cart.total) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
      <button class="checkout" @click="emit('checkout')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>{{ t('cart.checkout') }}
      </button>
      <p class="free-note" v-if="cart.total < 250">{{ t('cart.freeNoteAdd', { amount: ar(250 - cart.total) }) }}</p>
      <p class="free-note" v-else>{{ t('cart.freeNoteQualified') }}</p>
    </div>
  </aside>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'

defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'checkout'])

const { t } = useI18n()
const cart = useCartStore()
const ar = (n) => String(n)
</script>
