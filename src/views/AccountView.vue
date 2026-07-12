<template>
  <div class="portal">
    <PortalBar drawer>
      <nav class="tabs">
        <RouterLink :to="{ name: 'account-profile' }">{{ t('account.profileTab') }}</RouterLink>
        <RouterLink :to="{ name: 'account-orders' }">{{ t('account.orders') }}</RouterLink>
      </nav>
    </PortalBar>
    <main class="portal-body">
      <h1>{{ t('account.title') }}</h1>
      <p class="a-muted" v-if="auth.user">{{ t('account.greeting', { name: auth.user.full_name || auth.user.email }) }} · <span dir="ltr">{{ auth.user.email }}</span></p>
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import PortalBar from '../components/PortalBar.vue'

const { t } = useI18n()
const auth = useAuthStore()
</script>

<style scoped>
.portal { min-height: 100vh; background: var(--cream, #f7f3e9); }
.portal-body { max-width: 820px; margin: 0 auto; padding: 1.8rem 1.2rem 4rem; }
.portal-body h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 2rem; }
</style>
