<template>
  <!-- one glyph per point so the rating is readable without colour, and announced
       once as a whole rather than as five separate stars -->
  <span class="stars" role="img" :aria-label="t('reviews.starsAria', { n: value })">
    <span v-for="n in 5" :key="n" :class="{ on: n <= value }">★</span>
  </span>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({ value: { type: Number, default: 0 } })
const { t } = useI18n()
</script>

<style scoped>
.stars { display: inline-flex; gap: .08em; font-size: 1rem; line-height: 1; letter-spacing: .04em; }
.stars span { color: rgba(60,74,39,.22); }
.stars span.on { color: var(--gold); }
</style>
