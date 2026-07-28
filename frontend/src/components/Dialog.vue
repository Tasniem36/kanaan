<template>
  <transition name="v">
    <div class="modal-overlay" v-if="open" @click.self="$emit('close')">
      <div class="co" :style="maxWidth ? { maxWidth } : null">
        <button class="dlg-close" @click="$emit('close')" :aria-label="t('common.close')">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>
        </button>
        <h3 v-if="title" class="dlg-title">{{ title }}</h3>
        <slot />
      </div>
    </div>
  </transition>
</template>

<script setup>
// Shared modal dialog: overlay + centered card + close button + optional title.
// The card is `.co`, so `.co-l` / `.grid2` form helpers work inside the slot.
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  maxWidth: { type: String, default: '' },
})
defineEmits(['close'])
</script>

<style scoped>
.dlg-close {
  position: absolute; top: .8rem; inset-inline-start: .8rem;
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--cream-2); color: var(--green);
  display: grid; place-items: center;
}
.dlg-title {
  font-family: 'Amiri', serif; font-size: 1.5rem; color: var(--green);
  text-align: center; margin-bottom: .8rem;
}
</style>
