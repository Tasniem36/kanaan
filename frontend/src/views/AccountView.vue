<template>
  <div class="portal">
    <PortalBar drawer>
      <nav class="tabs">
        <RouterLink :to="{ name: 'account-profile' }">{{ t('account.profileTab') }}</RouterLink>
        <RouterLink :to="{ name: 'account-orders' }">{{ t('account.orders') }}</RouterLink>
        <RouterLink :to="{ name: 'account-wishlist' }">
          {{ t('wishlist.title') }}<span v-if="wishlist.count" class="wcount">{{ wishlist.count }}</span>
        </RouterLink>
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
import { useWishlistStore } from '../stores/wishlist'
import PortalBar from '../components/PortalBar.vue'

const { t } = useI18n()
const auth = useAuthStore()
const wishlist = useWishlistStore()
</script>

<style scoped>
.portal { min-height: 100vh; background: var(--cream, #f7f3e9); }
.portal-body { max-width: 820px; margin: 0 auto; padding: 1.8rem 1.2rem 4rem; }
.portal-body h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 2rem; }
.wcount {
  display: inline-grid; place-items: center;
  min-width: 18px; height: 18px; padding: 0 5px;
  margin-inline-start: .35rem; border-radius: 9px;
  background: var(--red, #9c2b2b); color: #fff;
  font-size: .72rem; font-weight: 700; vertical-align: middle;
}
</style>
