<template>
  <RouterView />
  <ConfirmDialog />
  <ToastHost />
</template>

<script setup>
import { RouterView } from 'vue-router'
import ConfirmDialog from './components/ConfirmDialog.vue'
import ToastHost from './components/ToastHost.vue'
</script>
