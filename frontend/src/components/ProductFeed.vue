<template>
  <div>
    <div ref="root" class="grid">
      <ProductCard
        v-for="(p, i) in items"
        :key="p.id"
        :product="p"
        :index="i % pageSize"
        @added="$emit('added', $event)"
      />
    </div>
    <!-- sentinel: loads the next 10 when it scrolls into view -->
    <div v-if="hasMore" ref="sentinel" class="load-more"><span class="ld-spin"></span></div>
    <p v-else-if="!items.length && !loading" class="a-muted" style="text-align:center">{{ emptyText }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import ProductCard from './ProductCard.vue'
import { api } from '../services/api'

const props = defineProps({
  category: { type: String, default: '' },
  pageSize: { type: Number, default: 10 },
  emptyText: { type: String, default: '' },
})
defineEmits(['added'])

const items = ref([])
const total = ref(0)
const loaded = ref(false)
const loading = ref(false)
const root = ref(null)
const sentinel = ref(null)
const hasMore = computed(() => !loaded.value || items.value.length < total.value)

let io = null

async function loadMore() {
  if (loading.value || (loaded.value && items.value.length >= total.value)) return
  loading.value = true
  try {
    const qs = new URLSearchParams({ limit: props.pageSize, offset: items.value.length, active: '1' })
    if (props.category) qs.set('category', props.category)
    const { products, total: t } = await api(`/products?${qs}`)
    items.value.push(...products)
    total.value = t
    loaded.value = true
    nextTick(revealCards)
  } catch {
    loaded.value = true // stop retrying on error
  } finally {
    loading.value = false
    nextTick(arm)
  }
}

function revealCards() {
  root.value?.querySelectorAll('.reveal:not(.in)').forEach((el) => el.classList.add('in'))
}
// re-observe after each load so a short batch keeps filling the viewport
function arm() {
  if (io) io.disconnect()
  if (!sentinel.value) return
  io = new IntersectionObserver(
    (entries) => { if (entries.some((e) => e.isIntersecting)) loadMore() },
    { rootMargin: '400px 0px' }
  )
  io.observe(sentinel.value)
}

// let the parent refresh (e.g. after an order changes stock)
function reload() {
  items.value = []
  total.value = 0
  loaded.value = false
  loadMore()
}
defineExpose({ reload })

onMounted(loadMore)
onBeforeUnmount(() => io && io.disconnect())
</script>
