<template>
  <div class="loader" role="status" :aria-label="label || 'loading'">
    <span class="ld-spin"></span>
    <span v-if="label" class="ld-label">{{ label }}</span>
  </div>
</template>

<script setup>
// small, centered spinner used anywhere we're waiting on an API response
defineProps({ label: { type: String, default: '' } })
</script>

<style scoped>
.loader { display: grid; place-items: center; gap: .7rem; padding: 2.5rem 0; }
.ld-label { color: var(--muted); font-size: .9rem; }
/* .ld-spin itself is styled globally in style.css */
</style>
