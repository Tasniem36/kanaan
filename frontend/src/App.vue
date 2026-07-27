<template>
  <RouterView v-slot="{ Component }">
    <!-- keep the storefront alive so its infinite-scroll feed + scroll position
         survive a trip into a product page and back -->
    <keep-alive include="HomeView">
      <component :is="Component" />
    </keep-alive>
  </RouterView>
  <ConfirmDialog />
  <ToastHost />
</template>

<script setup>
import { RouterView } from 'vue-router'
import ConfirmDialog from './components/ConfirmDialog.vue'
import ToastHost from './components/ToastHost.vue'
</script>
