<template>
  <!-- A cancelled order didn't travel the normal path, so a progress track would
       misrepresent it — show the plain fact instead. -->
  <p v-if="cancelled" class="ot-cancelled">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>
    {{ t('status.cancelled') }}<span v-if="cancelledAt" class="a-muted"> · {{ fmt(cancelledAt) }}</span>
  </p>

  <ol v-else class="ot" :style="{ '--done': doneRatio }">
    <li v-for="s in steps" :key="s.key" :class="['ot-step', { done: s.done, now: s.current }]">
      <span class="ot-dot" aria-hidden="true">
        <svg v-if="s.done && !s.current" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>
      </span>
      <span class="ot-label">{{ t(`status.${s.key}`) }}</span>
      <span class="ot-at">{{ s.at ? fmt(s.at) : '' }}</span>
    </li>
  </ol>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// The happy path a customer's order walks. 'pending' and 'paid' are the same
// stage from the shopper's point of view (the order is in), so they share a step
// — otherwise cash-on-delivery orders would look stuck at step one forever.
const STEPS = [
  { key: 'paid', matches: ['pending', 'paid'] },
  { key: 'preparing', matches: ['preparing'] },
  { key: 'fulfilled', matches: ['fulfilled'] },
  { key: 'delivered', matches: ['delivered'] },
]

const props = defineProps({
  status: { type: String, required: true },
  // [{ status, created_at }] in chronological order, from GET /orders
  events: { type: Array, default: () => [] },
})

const { t, locale } = useI18n()

const cancelled = computed(() => props.status === 'cancelled')
const cancelledAt = computed(() => props.events.find((e) => e.status === 'cancelled')?.created_at || null)

// index of the stage the order is currently in
const activeIndex = computed(() => {
  const i = STEPS.findIndex((s) => s.matches.includes(props.status))
  return i === -1 ? 0 : i
})

const steps = computed(() =>
  STEPS.map((s, i) => ({
    key: s.key,
    done: i <= activeIndex.value,
    current: i === activeIndex.value,
    // earliest event matching this stage — the moment it was actually reached
    at: props.events.find((e) => s.matches.includes(e.status))?.created_at || null,
  }))
)

// how far the connecting line is filled, 0–1
const doneRatio = computed(() => (STEPS.length < 2 ? 0 : activeIndex.value / (STEPS.length - 1)))

const fmt = (d) =>
  new Date(d).toLocaleString(locale.value, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
</script>

<style scoped>
.ot {
  --dot: 22px;
  position: relative;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  list-style: none;
  margin: 0.9rem 0 0.2rem;
  padding: 0;
}
/* The track runs behind the dots, from the first dot's centre to the last. With
   4 equal columns those centres sit at 12.5% and 87.5%, hence the 75% span.
   Anchoring with inset-inline-start makes it fill the right way round in RTL. */
.ot::before, .ot::after {
  content: "";
  position: absolute;
  top: calc(var(--dot) / 2 - 1px);
  inset-inline-start: 12.5%;
  height: 2px;
  border-radius: 2px;
}
.ot::before { width: 75%; background: rgba(60, 74, 39, 0.16); }
.ot::after {
  width: calc(75% * var(--done));
  background: var(--green, #3c4a27);
  transition: width 0.4s ease;
}

.ot-step {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 0.3rem;
  text-align: center;
}
.ot-dot {
  width: var(--dot);
  height: var(--dot);
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--cream, #f5efe3);
  border: 2px solid rgba(60, 74, 39, 0.22);
  color: #fff;
  z-index: 1;
  transition: background 0.3s, border-color 0.3s;
}
.ot-dot svg { width: 12px; height: 12px; }
.done .ot-dot { background: var(--green, #3c4a27); border-color: var(--green, #3c4a27); }
/* the current stage pulses gently so the eye lands on "where is it now" */
.now .ot-dot {
  background: var(--gold, #b8902f);
  border-color: var(--gold, #b8902f);
  box-shadow: 0 0 0 4px rgba(184, 144, 47, 0.22);
}
.ot-label { font-size: 0.74rem; font-weight: 700; color: var(--muted, #7b7768); line-height: 1.25; }
.done .ot-label { color: var(--green, #3c4a27); }
.now .ot-label { color: var(--terra-deep, #7a3b2e); }
.ot-at { font-size: 0.66rem; color: var(--muted, #7b7768); min-height: 0.9em; }

.ot-cancelled {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0.8rem 0 0.2rem;
  font-size: 0.86rem;
  font-weight: 700;
  color: var(--red, #9c2b2b);
}
.ot-cancelled svg { width: 15px; height: 15px; }

@media (max-width: 420px) {
  .ot-label { font-size: 0.68rem; }
  .ot-at { display: none; }
}
</style>
