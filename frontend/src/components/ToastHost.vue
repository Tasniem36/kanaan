<template>
  <transition name="v">
    <div class="toast" v-if="toast.message">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>
      {{ toast.message }}
    </div>
  </transition>
</template>

<script setup>
import { useToastStore } from '../stores/toast'
const toast = useToastStore()
</script>
