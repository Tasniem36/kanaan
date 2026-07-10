<template>
  <div class="user-menu" ref="root">
    <button class="avatar" @click="open = !open" :aria-label="t('nav.account')" :aria-expanded="open">
      <span v-if="auth.isAuthenticated" class="initial">{{ initial }}</span>
      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>
    </button>

    <transition name="v">
      <div v-if="open" class="menu">
        <!-- signed in -->
        <template v-if="auth.isAuthenticated">
          <div class="menu-head">
            <b>{{ auth.user?.full_name || t('nav.account') }}</b>
            <span dir="ltr">{{ auth.user?.email }}</span>
          </div>
          <RouterLink to="/account" class="menu-item" @click="open = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>
            {{ t('nav.account') }}
          </RouterLink>
          <RouterLink v-if="auth.isManager" to="/manager" class="menu-item" @click="open = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            {{ t('nav.admin') }}
          </RouterLink>
        </template>

        <!-- signed out -->
        <template v-else>
          <RouterLink to="/login" class="menu-item" @click="open = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"/></svg>
            {{ t('nav.login') }}
          </RouterLink>
          <RouterLink to="/register" class="menu-item" @click="open = false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="4"/><path d="M3 21a6 6 0 0 1 12 0M18 8v6M21 11h-6"/></svg>
            {{ t('auth.createAccount') }}
          </RouterLink>
        </template>

        <!-- shared: language (+ logout when signed in) -->
        <button class="menu-item" @click="toggleLang">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></svg>
          {{ locale === 'ar' ? 'English' : 'العربية' }}
        </button>
        <button v-if="auth.isAuthenticated" class="menu-item danger" @click="logout">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>
          {{ t('account.logout') }}
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { setLocale } from '../i18n'

const { t, locale } = useI18n()
const auth = useAuthStore()
const router = useRouter()

const open = ref(false)
const root = ref(null)

// avatar shows the first letter of the email when signed in
const initial = computed(() => (auth.user?.email || '?').trim().charAt(0).toUpperCase())

function toggleLang() {
  setLocale(locale.value === 'ar' ? 'en' : 'ar')
}

function logout() {
  open.value = false
  auth.logout()
  router.push('/')
}

function onDocClick(e) {
  if (open.value && root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.user-menu { position: relative; }
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--green, #3c4a27);
  color: #fff;
  display: grid;
  place-items: center;
  cursor: pointer;
}
.avatar svg { width: 22px; height: 22px; }
.avatar .initial { font-weight: 700; font-size: 0.95rem; line-height: 1; }
.avatar:hover { filter: brightness(1.08); }
.menu {
  position: absolute;
  inset-inline-start: 0;
  top: calc(100% + 0.5rem);
  min-width: 230px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 16px 44px rgba(30, 34, 20, 0.18);
  padding: 0.4rem;
  z-index: 60;
}
.menu-head {
  padding: 0.6rem 0.7rem;
  border-bottom: 1px solid rgba(60, 74, 39, 0.1);
  margin-bottom: 0.3rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.menu-head b { color: var(--green, #3c4a27); font-size: 0.95rem; }
.menu-head span { color: #8a8c7c; font-size: 0.78rem; }
.menu-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.6rem 0.7rem;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink, #2b2b22);
  cursor: pointer;
  text-align: start;
}
.menu-item svg { width: 18px; height: 18px; opacity: 0.8; flex-shrink: 0; }
.menu-item:hover { background: rgba(60, 74, 39, 0.08); }
.menu-item.danger { color: var(--red, #9c2b2b); }
.menu-item.danger:hover { background: rgba(156, 43, 43, 0.1); }
</style>
