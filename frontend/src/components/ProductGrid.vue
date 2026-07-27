<template>
  <div>
    <div ref="root" class="grid">
      <ProductCard
        v-for="(p, i) in visible"
        :key="p.id"
        :product="p"
        :index="i % pageSize"
        @added="$emit('added', $event)"
      />
    </div>
    <Pager v-model="page" :pages="pageCount" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import ProductCard from './ProductCard.vue'
import Pager from './Pager.vue'
import { usePagination } from '../composables/usePagination'

const props = defineProps({
  items: { type: Array, default: () => [] },
  pageSize: { type: Number, default: 10 },
})
defineEmits(['added'])

const root = ref(null)
const { page, pageCount, visible } = usePagination(() => props.items, props.pageSize)

// reveal rendered cards immediately (never gate visibility on scroll)
function revealCards() {
  if (!root.value) return
  root.value.querySelectorAll('.reveal:not(.in)').forEach((el) => el.classList.add('in'))
}
onMounted(() => nextTick(revealCards))
watch([() => props.items.length, visible], () => nextTick(revealCards))
</script>
