<template>
  <button class="lang-toggle" @click="toggle" :aria-label="locale === 'ar' ? 'Switch to English' : 'التبديل إلى العربية'">
    {{ locale === 'ar' ? 'EN' : 'ع' }}
  </button>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { setLocale } from '../i18n'

const { locale } = useI18n()

function toggle() {
  setLocale(locale.value === 'ar' ? 'en' : 'ar')
}
</script>

<style scoped>
.lang-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-weight: 700;
  font-size: 0.85rem;
  min-width: 40px;
  height: 32px;
  padding: 0 0.6rem;
  border-radius: 10px;
  background: rgba(60, 74, 39, 0.08);
  color: var(--green, #3c4a27);
  cursor: pointer;
  line-height: 1;
}
.lang-toggle:hover { background: rgba(60, 74, 39, 0.16); }
</style>
