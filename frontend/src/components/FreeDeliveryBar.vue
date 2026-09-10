<template>
  <!-- role=status, not alert: it updates as the basket grows and a screen reader
       should mention it in passing, not interrupt what is being read. -->
  <div v-if="threshold > 0 && settings.deliveryLoaded" class="fd" :class="[variant, { done, hidden }]" role="status">
    <p class="fd-msg">{{ message }}</p>
    <!-- no progress line on an empty basket: a bar sitting at 0% reads as failure
         rather than an invitation -->
    <div v-if="cart.count" class="fd-track"><span class="fd-fill" :style="{ width: pct + '%' }"></span></div>
  </div>
</template>

<script setup>
// How close this basket is to free delivery, in two shapes:
//
//   strip — a slim band under the sticky header, on every storefront page. The
//           offer used to live inside the cart drawer, which meant the only people
//           who learned about it were the ones who had already opened their basket.
//   panel — the block in the drawer footer, where it has always been.
//
// One component for both so the two can never disagree about the number, which is
// the whole risk of saying it twice.
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'
import { useSettingsStore } from '../stores/settings'

const props = defineProps({ variant: { type: String, default: 'panel' } })

const { t } = useI18n()
const cart = useCartStore()
const settings = useSettingsStore()

const threshold = computed(() => Number(settings.delivery?.free_threshold) || 0)
const done = computed(() => threshold.value > 0 && cart.total >= threshold.value)
// Rounded up: telling someone to add 284.5 درهم is not an instruction anyone can
// follow, and rounding down would leave them a few fils short of the offer.
const remaining = computed(() => Math.max(0, Math.ceil(threshold.value - cart.total)))
const pct = computed(() => (threshold.value > 0
  ? Math.min(100, Math.round((cart.total / threshold.value) * 100)) : 0))

const message = computed(() => {
  if (done.value) return t('cart.freeNoteQualified')
  if (cart.count) return t('cart.freeNoteAdd', { amount: remaining.value })
  // Nothing in the basket yet: state the offer rather than a distance from it.
  return t('cart.freeNoteFrom', { amount: threshold.value })
})

// The threshold has a default in the store, so an unfetched config would quietly
// advertise the wrong number. Until this lands the bar renders nothing at all —
// better silent for a moment than wrong out loud. Only the home page and the opened
// drawer used to fetch it, which left the category, product and search pages
// showing whatever the default happened to be.
// --- out of the way while reading, back on the way up ----------------------
// Scrolling down is reading; the band folds away and gives the screen back.
// Scrolling up is looking for something, which is when it is worth seeing again.
// The header itself stays put — only the band moves.
const hidden = ref(false)
const TOP = 80        // near the top nothing has been scrolled past, so always show
const JITTER = 6      // a fingertip resting on a phone moves a pixel or two

let lastY = 0
let queued = false

function onScroll() {
  if (queued) return
  queued = true
  requestAnimationFrame(() => {
    const y = window.scrollY
    if (y < TOP) hidden.value = false
    else if (Math.abs(y - lastY) > JITTER) hidden.value = y > lastY
    lastY = y
    queued = false
  })
}

// Adding something to the basket changes what the band says, and that is exactly
// the moment worth showing: they are one jar closer than the last time they looked.
watch(() => cart.count, () => { hidden.value = false })

onMounted(() => {
  if (!settings.deliveryLoaded) settings.fetchDelivery()
  // Only the band under the header folds away. The drawer's copy has nowhere to go
  // and is mounted for the life of the page, so it must not put a listener on every
  // scroll of every storefront page for nothing.
  if (import.meta.env.SSR || props.variant !== 'strip') return
  lastY = window.scrollY
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<style scoped>
.fd-fill { display: block; height: 100%; border-radius: 999px; background: var(--gold, #b8902f); transition: width .4s ease; }
.fd.done .fd-fill { background: var(--green, #3c4a27); }
.fd-msg { font-weight: 700; color: var(--green, #3c4a27); margin: 0; }

/* --- the band under the header ------------------------------------------- */
.fd.strip {
  position: relative;
  padding: .36rem 1rem .46rem;
  text-align: center;
  background: linear-gradient(180deg, rgba(184,144,47,.16), rgba(184,144,47,.06));
  border-top: 1px solid rgba(184,144,47,.28);
  overflow: hidden;
  max-height: 4rem;
  transition: max-height .28s ease, opacity .2s ease, padding .28s ease;
}
/* folded away rather than slid up: the band sits under the header inside the same
   sticky block, so anything that moved it would slide it behind the bar */
.fd.strip.hidden {
  max-height: 0; opacity: 0;
  padding-top: 0; padding-bottom: 0; border-top-width: 0;
}
@media (prefers-reduced-motion: reduce) { .fd.strip { transition: none; } }
.fd.strip.done {
  background: linear-gradient(180deg, rgba(60,74,39,.15), rgba(60,74,39,.05));
  border-top-color: rgba(60,74,39,.3);
}
.fd.strip .fd-msg { font-size: .8rem; line-height: 1.35; }
/* the progress line rides the bottom edge of the band — inset-inline so it runs
   the right way round in both directions */
.fd.strip .fd-track {
  position: absolute; inset-inline: 0; bottom: 0;
  height: 3px; background: rgba(60,74,39,.12);
}
@media (max-width: 560px) { .fd.strip .fd-msg { font-size: .74rem; } }

/* --- the block in the cart drawer ---------------------------------------- */
.fd.panel {
  margin-bottom: .9rem; padding: .6rem .8rem; border-radius: 12px;
  background: var(--cream-2, rgba(60,74,39,.08)); border: 1px solid rgba(184,144,47,.35);
}
.fd.panel.done { border-color: var(--green, #3c4a27); background: rgba(60,74,39,.09); }
.fd.panel .fd-msg { font-size: .85rem; margin-bottom: .45rem; line-height: 1.4; }
.fd.panel .fd-track { height: 7px; border-radius: 999px; background: rgba(60,74,39,.15); overflow: hidden; }
</style>
