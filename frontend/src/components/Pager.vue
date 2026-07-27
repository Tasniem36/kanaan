<template>
  <nav v-if="pages > 1" class="pager" aria-label="pagination">
    <button class="pg-btn pg-arrow" :disabled="modelValue <= 1" @click="go(modelValue - 1)" aria-label="prev">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
    </button>
    <button v-for="(p, i) in pageList" :key="i" class="pg-btn" :class="{ on: p === modelValue }" :disabled="p === '…'" @click="p !== '…' && go(p)">{{ p }}</button>
    <button class="pg-btn pg-arrow" :disabled="modelValue >= pages" @click="go(modelValue + 1)" aria-label="next">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Number, default: 1 },
  pages: { type: Number, default: 1 },
})
const emit = defineEmits(['update:modelValue'])

function go(p) {
  if (p >= 1 && p <= props.pages && p !== props.modelValue) emit('update:modelValue', p)
}

// compact list: 1 … (current-1, current, current+1) … last
const pageList = computed(() => {
  const n = props.pages
  const c = props.modelValue
  const out = []
  for (let i = 1; i <= n; i++) {
    if (i === 1 || i === n || (i >= c - 1 && i <= c + 1)) out.push(i)
    else if (out[out.length - 1] !== '…') out.push('…')
  }
  return out
})
</script>

<style scoped>
.pager { display: flex; gap: 0.35rem; justify-content: center; align-items: center; margin-top: 1.2rem; flex-wrap: wrap; }
.pg-btn {
  min-width: 36px; height: 36px; padding: 0 0.5rem;
  display: grid; place-items: center;
  border-radius: 10px; background: rgba(60, 74, 39, 0.08);
  color: var(--green, #3c4a27); font-weight: 700; font-size: 0.9rem; cursor: pointer;
}
.pg-btn.on { background: var(--green, #3c4a27); color: #fff; }
.pg-btn:disabled { opacity: 0.4; cursor: default; }
.pg-btn:not(:disabled):hover { background: rgba(60, 74, 39, 0.16); }
.pg-arrow svg { width: 18px; height: 18px; }
/* chevrons point the right way in RTL */
[dir="rtl"] .pg-arrow svg { transform: scaleX(-1); }
</style>
