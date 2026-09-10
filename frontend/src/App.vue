<template>
  <RouterView v-slot="{ Component }">
    <!-- keep the storefront + category pages alive so their infinite-scroll feed
         and scroll position survive a trip into a product page and back -->
    <keep-alive include="HomeView,CategoryView">
      <component :is="Component" />
    </keep-alive>
  </RouterView>
  <ConfirmDialog />
  <ToastHost />
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import ConfirmDialog from './components/ConfirmDialog.vue'
import ToastHost from './components/ToastHost.vue'
import { useCartStore } from './stores/cart'
import { settleAwaited } from './services/awaitingPayment'

// A payment the return page never got an answer about may have been settled by the
// server since — see services/awaitingPayment. Costs nothing for everyone else.
onMounted(() => { settleAwaited(useCartStore()) })
</script>
