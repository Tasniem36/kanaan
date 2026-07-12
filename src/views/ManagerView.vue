<template>
  <div class="portal">
    <PortalBar drawer>
      <nav class="tabs">
        <RouterLink :to="{ name: 'manager-orders' }">{{ t('manager.orders') }}</RouterLink>
        <RouterLink :to="{ name: 'manager-products' }">{{ t('manager.products') }}</RouterLink>
        <RouterLink :to="{ name: 'manager-clients' }">{{ t('manager.clients') }}</RouterLink>
      </nav>
    </PortalBar>
    <main class="portal-body">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PortalBar from '../components/PortalBar.vue'

const { t } = useI18n()
</script>

<style scoped>
.portal { min-height: 100vh; background: var(--cream, #f7f3e9); }
.portal-body { max-width: 1000px; margin: 0 auto; padding: 1.8rem 1.2rem 4rem; }
</style>
