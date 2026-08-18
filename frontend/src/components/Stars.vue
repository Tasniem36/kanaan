<template>
  <!-- Two stacked rows of five glyphs: a muted one underneath, and a gold one
       clipped to the rating's width on top. That way a fractional value shows as a
       part-filled star instead of being rounded — a 4.6 average sitting next to
       five solid stars reads as a contradiction.
       Announced once as a whole, rather than as five separate stars. -->
  <span class="stars" role="img" :aria-label="t('reviews.starsAria', { n: rounded })">
    <span class="row" aria-hidden="true">★★★★★</span>
    <span class="row fill" :style="{ width: pct }" aria-hidden="true">★★★★★</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({ value: { type: Number, default: 0 } })
const { t } = useI18n()

const clamped = computed(() => Math.min(5, Math.max(0, Number(props.value) || 0)))
const pct = computed(() => `${(clamped.value / 5) * 100}%`)
// screen readers get one decimal at most, and no trailing '.0'
const rounded = computed(() => Math.round(clamped.value * 10) / 10)
</script>

<style scoped>
.stars {
  position: relative; display: inline-block;
  font-size: 1rem; line-height: 1; letter-spacing: .04em;
}
/* the empty row borrows the surrounding text colour, so it reads as "unfilled" on
   the cream dashboard and on the dark reviews section alike */
.row { display: block; white-space: nowrap; opacity: .22; }
.fill {
  position: absolute; inset-block-start: 0; inset-inline-start: 0;
  overflow: hidden; color: var(--gold); opacity: 1;
}
</style>
