<template>
  <header class="portal-bar" :class="{ scrolled }">
    <div class="pb-lead">
      <UserMenu />
      <RouterLink to="/" class="pbrand"><span class="g">دكّان</span> كنعان</RouterLink>
    </div>
    <div class="pb-center"><slot /></div>
    <div class="pb-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import UserMenu from './UserMenu.vue'

defineProps({ scrolled: { type: Boolean, default: false } })
</script>

<style scoped>
.portal-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.55rem 1.4rem;
  background: rgba(245, 239, 227, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(60, 74, 39, 0.12);
  position: sticky;
  top: 0;
  z-index: 60;
  transition: box-shadow 0.3s;
}
.portal-bar.scrolled { box-shadow: 0 10px 30px -18px rgba(44, 55, 25, 0.5); }
.pb-lead { flex: 1; display: flex; align-items: center; gap: 0.7rem; }
.pbrand { font-family: 'Aref Ruqaa', 'Amiri', serif; font-size: 1.6rem; color: var(--green, #3c4a27); white-space: nowrap; }
.pbrand .g { color: var(--gold, #b8902f); }
.pb-center { display: flex; justify-content: center; }
.pb-actions { flex: 1; display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem; }
</style>
