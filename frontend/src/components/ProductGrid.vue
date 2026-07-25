<template>
  <div ref="root" class="grid">
    <ProductCard
      v-for="(p, i) in visible"
      :key="p.id"
      :product="p"
      :index="i % pageSize"
      @added="$emit('added', $event)"
    />
    <!-- loads the next batch when it scrolls into view -->
    <div v-if="visible.length < items.length" ref="sentinel" class="grid-sentinel" aria-hidden="true">
      <span class="grid-spinner"></span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import ProductCard from './ProductCard.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  pageSize: { type: Number, default: 8 },
})
defineEmits(['added'])

const root = ref(null)
const sentinel = ref(null)
const shown = ref(props.pageSize)
const visible = computed(() => props.items.slice(0, shown.value))

let loadIO = null

function loadMore() {
  shown.value = Math.min(shown.value + props.pageSize, props.items.length)
}

// (re)arm the sentinel observer; re-observing fires a fresh callback with the
// current intersection state, so a batch that doesn't fill the viewport keeps loading
function attachLoader() {
  if (loadIO) loadIO.disconnect()
  if (!sentinel.value) return
  loadIO = new IntersectionObserver(
    (entries) => { if (entries.some((e) => e.isIntersecting)) loadMore() },
    { rootMargin: '600px 0px' }
  )
  loadIO.observe(sentinel.value)
}

// Reveal rendered cards immediately (a light fade via .reveal→.in). We do NOT
// gate visibility on scroll here — otherwise cards below the fold can stay
// hidden on mobile and look like "missing products".
function revealCards() {
  if (!root.value) return
  root.value.querySelectorAll('.reveal:not(.in)').forEach((el) => el.classList.add('in'))
}

onMounted(() => nextTick(() => { revealCards(); attachLoader() }))

watch([() => props.items.length, shown], () => nextTick(() => { revealCards(); attachLoader() }))

// if the source list shrinks (e.g. a product is removed), keep shown in range
watch(() => props.items.length, (n) => { if (shown.value > n) shown.value = Math.max(props.pageSize, n) })

onBeforeUnmount(() => loadIO && loadIO.disconnect())
</script>

<style scoped>
.grid-sentinel { grid-column: 1 / -1; display: grid; place-items: center; padding: 1.4rem 0; }
.grid-spinner {
  width: 26px; height: 26px; border-radius: 50%;
  border: 3px solid rgba(60, 74, 39, .18); border-top-color: var(--green, #3c4a27);
  animation: gspin .7s linear infinite;
}
@keyframes gspin { to { transform: rotate(360deg); } }
</style>
