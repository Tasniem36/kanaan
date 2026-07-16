<template>
  <header class="portal-bar" :class="{ scrolled, 'has-drawer': drawer }">
    <div class="pb-lead">
      <UserMenu />
      <RouterLink to="/" class="pbrand"><span class="g">دكّان</span> كنعان</RouterLink>
    </div>
    <div class="pb-center"><slot /></div>
    <div class="pb-actions">
      <slot name="actions" />
      <button v-if="drawer" class="burger" @click="open = true" aria-label="menu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
    </div>
  </header>

  <!-- mobile sidebar for the nav tabs (opt-in via the `drawer` prop) -->
  <template v-if="drawer">
    <transition name="v"><div v-if="open" class="mm-overlay" @click="open = false"></div></transition>
    <aside class="mobile-menu portal-drawer" :class="{ show: open }" aria-label="القائمة">
      <div class="mm-head">
        <span class="mm-brand"><span class="g">دكّان</span> كنعان</span>
        <button class="mm-close" @click="open = false" aria-label="إغلاق"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
      </div>
      <div class="mm-links" @click="open = false"><slot /></div>
    </aside>
  </template>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import UserMenu from './UserMenu.vue'

defineProps({ scrolled: { type: Boolean, default: false }, drawer: { type: Boolean, default: false } })
const open = ref(false)
</script>

<style scoped>
.portal-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.55rem 1.4rem;
  background: var(--cream, #f5efe3);
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
