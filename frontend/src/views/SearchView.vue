<template>
  <div class="search-page">
    <PortalBar :scrolled="scrolled" search>
      <template #actions>
        <button class="cart-btn" @click="openCart = true" aria-label="cart">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
          <span v-if="cart.count" class="badge">{{ cart.count }}</span>
        </button>
      </template>
    </PortalBar>

    <main class="wrap sr-body">
      <a href="/" class="sr-back" @click.prevent="backToStore">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M15 6l-6 6 6 6"/></svg>
        {{ t('product.backToStore') }}
      </a>

      <div class="sec-head">
        <span class="eyebrow">{{ t('search.resultsTitle') }}</span>
        <h1 class="display">{{ q || t('search.placeholder') }}</h1>
      </div>

      <template v-if="q">
        <ProductFilters
          v-model:sort="sort"
          v-model:min-price="minPrice"
          v-model:max-price="maxPrice"
        />
        <ProductFeed
          :q="q"
          :sort="sort"
          :min-price="minPrice"
          :max-price="maxPrice"
          :page-size="12"
          :empty-text="t('search.noResults')"
          @added="onAdded"
        />
      </template>
      <p v-else class="a-muted sr-hint">{{ t('search.startTyping') }}</p>
    </main>

    <CartDrawer :open="openCart" @close="openCart = false" @checkout="goCheckout" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useHead } from '@unhead/vue'
import { useCartStore } from '../stores/cart'
import { useToastStore } from '../stores/toast'
import { pName } from '../utils/product'
import PortalBar from '../components/PortalBar.vue'
import CartDrawer from '../components/CartDrawer.vue'
import ProductFeed from '../components/ProductFeed.vue'
import ProductFilters from '../components/ProductFilters.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const toast = useToastStore()

const openCart = ref(false)
const scrolled = ref(false)
const sort = ref('featured')
const minPrice = ref('')
const maxPrice = ref('')

// The term comes from the URL, so a search is shareable and the back button
// walks through previous searches.
const q = computed(() => String(route.query.q || '').trim())

// A search results page has nothing to offer a crawler, and indexing arbitrary
// query strings is how sites end up with thousands of junk URLs in Google.
useHead({
  title: () => (q.value ? `${q.value} — دكّان كنعان` : 'دكّان كنعان'),
  meta: [{ name: 'robots', content: 'noindex, follow' }],
})

function onAdded(p) { toast.show(t('cart.added', { name: pName(p) })) }
function goCheckout() {
  openCart.value = false
  router.push({ name: 'home', query: { checkout: '1' } })
}
function backToStore() {
  if (window.history.state?.back) router.back()
  else router.push('/')
}

function onScroll() { scrolled.value = scrollY > 10 }
onMounted(() => addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => removeEventListener('scroll', onScroll))
</script>

<style scoped>
.search-page { min-height: 100vh; background: var(--cream); }
.sr-body { padding: 1.4rem 0 4rem; }
.sr-back { display: inline-flex; align-items: center; gap: .3rem; color: var(--green); font-weight: 700; margin-bottom: 1.2rem; }
.sr-back:hover { color: var(--gold); }
[dir="rtl"] .sr-back svg { transform: scaleX(-1); }
.sec-head { text-align: center; margin-bottom: 1.6rem; }
.sec-head h1 { font-family: 'Amiri', serif; color: var(--green); font-size: clamp(1.6rem, 4vw, 2.4rem); margin-top: .4rem; }
.sr-hint { text-align: center; padding: 2rem 0; }
</style>
