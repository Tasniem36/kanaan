<template>
  <div class="pw-wrap">
    <input
      :type="show ? 'text' : 'password'"
      class="a-input"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      v-bind="$attrs"
    >
    <button type="button" class="pw-toggle" @click="show = !show" :aria-label="show ? t('auth.hidePw') : t('auth.showPw')">
      <svg v-if="!show" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18M10.6 10.6a3 3 0 0 0 4.2 4.2M9.9 4.2A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.1 6.1A17 17 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 3-.5"/></svg>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineOptions({ inheritAttrs: false })
defineProps({ modelValue: { type: String, default: '' } })
defineEmits(['update:modelValue'])

const { t } = useI18n()
const show = ref(false)
</script>

<style scoped>
.pw-wrap { position: relative; }
.pw-wrap .a-input { padding-inline-end: 2.6rem; }
.pw-toggle {
  position: absolute;
  inset-inline-end: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  color: var(--green, #3c4a27);
  opacity: 0.6;
  cursor: pointer;
}
.pw-toggle:hover { opacity: 1; }
.pw-toggle svg { width: 18px; height: 18px; }
</style>
