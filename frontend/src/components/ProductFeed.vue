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
    <!-- sentinel: loads the next page when it scrolls into view (not in preview mode) -->
    <div v-if="hasMore && !preview" ref="sentinel" class="load-more"><span class="ld-spin"></span></div>
    <!-- the shelf is exhausted: somewhere to say what comes next, rather than dropping
         the shopper straight into the footer -->
    <!-- not after a failure: the shelf isn't finished, it just stopped arriving -->
    <slot v-if="loaded && !hasMore && !failed && items.length" name="end" :total="total" />
    <!-- The request failed, which is not the same as the shelf being empty: telling a
         shopper "nothing matches your filters" when the shop couldn't be reached sends
         them fiddling with filters that were never the problem. Say so instead, and
         offer the retry — a dropped connection usually works the second time. -->
    <div v-if="failed && !loading" class="feed-failed">
      <p>{{ t('common.loadFailed') }}</p>
      <button class="btn btn-green" type="button" @click="reload">{{ t('common.retry') }}</button>
    </div>
    <p v-else-if="!items.length && !loading" class="a-muted" style="text-align:center">{{ emptyText }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ProductCard from './ProductCard.vue'
import { api } from '../services/api'

const { t } = useI18n()

const props = defineProps({
  category: { type: String, default: '' },
  type: { type: String, default: '' },
  q: { type: String, default: '' },
  // one of the keys in SORT_SQL on the API (featured | newest | price_asc | price_desc | name)
  sort: { type: String, default: '' },
  minPrice: { type: [Number, String], default: '' },
  maxPrice: { type: [Number, String], default: '' },
  pageSize: { type: Number, default: 10 },
  emptyText: { type: String, default: '' },
  // preview: load a single page and stop (no infinite scroll) — used for the
  // short home-page teasers that link out to the full category page
  preview: { type: Boolean, default: false },
})
// `results` fires once per query with how many matched — the search page reports it,
// because a term that finds nothing is the most useful thing in the log
const emit = defineEmits(['added', 'results'])

const items = ref([])
const total = ref(0)
const loaded = ref(false)
const loading = ref(false)
// the last request errored — kept apart from `loaded` so the empty grid can say which
// of the two happened
const failed = ref(false)
const root = ref(null)
const sentinel = ref(null)
const hasMore = computed(() => !loaded.value || items.value.length < total.value)

let io = null
// Bumped by reload(). A page already in flight when the filters change belongs to
// the old result set, so its rows must be dropped rather than appended.
let gen = 0

async function loadMore() {
  if (loading.value || (loaded.value && items.value.length >= total.value)) return
  loading.value = true
  const mine = gen
  try {
    const qs = new URLSearchParams({ limit: props.pageSize, offset: items.value.length, active: '1' })
    if (props.category) qs.set('category', props.category)
    if (props.type) qs.set('type', props.type)
    if (props.q) qs.set('q', props.q)
    if (props.sort) qs.set('sort', props.sort)
    if (props.minPrice !== '' && props.minPrice !== null) qs.set('min_price', props.minPrice)
    if (props.maxPrice !== '' && props.maxPrice !== null) qs.set('max_price', props.maxPrice)
    // named `n`, not `t`: `t` is the translator in this scope
    const { products, total: n } = await api(`/products?${qs}`)
    if (mine !== gen) return
    const first = !loaded.value
    items.value.push(...products)
    total.value = n
    loaded.value = true
    failed.value = false
    if (first) emit('results', n)
    nextTick(revealCards)
  } catch {
    if (mine === gen) {
      loaded.value = true // stop retrying on error
      failed.value = true
    }
  } finally {
    // only the current request may release the loading flag — a newer one has
    // already claimed it
    if (mine === gen) {
      loading.value = false
      nextTick(arm)
    }
  }
}

function revealCards() {
  root.value?.querySelectorAll('.reveal:not(.in)').forEach((el) => el.classList.add('in'))
}
// re-observe after each load so a short batch keeps filling the viewport
function arm() {
  if (io) io.disconnect()
  if (props.preview || !sentinel.value) return
  io = new IntersectionObserver(
    (entries) => { if (entries.some((e) => e.isIntersecting)) loadMore() },
    { rootMargin: '400px 0px' }
  )
  io.observe(sentinel.value)
}

// let the parent refresh (e.g. after an order changes stock)
function reload() {
  gen++            // invalidate whatever page is in flight
  items.value = []
  total.value = 0
  loaded.value = false
  loading.value = false
  failed.value = false
  loadMore()
}
defineExpose({ reload })

// changing any filter (chip, search term, sort, price range) restarts the feed
// from empty — offsets from the previous result set are meaningless afterwards
watch(() => [props.type, props.q, props.sort, props.minPrice, props.maxPrice], reload)

onMounted(loadMore)
onBeforeUnmount(() => io && io.disconnect())
</script>
