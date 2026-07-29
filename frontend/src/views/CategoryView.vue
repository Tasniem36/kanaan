<template>
  <div class="cat-page">
    <PortalBar :scrolled="scrolled">
      <template #actions>
        <button class="cart-btn" @click="openCart = true" aria-label="cart">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
          <span v-if="cart.count" class="badge">{{ cart.count }}</span>
        </button>
      </template>
    </PortalBar>

    <main class="wrap cat-body">
      <a href="/" class="cat-back" @click.prevent="backToStore">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M15 6l-6 6 6 6"/></svg>
        {{ t('product.backToStore') }}
      </a>

      <div class="sec-head">
        <span class="eyebrow">{{ t(meta.eyebrow) }}</span>
        <h1 class="display">{{ t(meta.title) }}</h1>
        <p>{{ t(meta.desc) }}</p>
      </div>

      <div v-if="types.length" class="type-filter">
        <button class="type-chip" :class="{ on: !type }" @click="type = ''">{{ t('home.allTypes') }}</button>
        <button v-for="ty in types" :key="ty" class="type-chip" :class="{ on: type === ty }" @click="type = ty">{{ ty }}</button>
      </div>

      <ProductFeed :key="activeCat" :category="activeCat" :type="type" :empty-text="t('search.noResults')" @added="onAdded" />
    </main>

    <CartDrawer :open="openCart" @close="openCart = false" @checkout="goCheckout" />
  </div>
</template>

<script>
// named so <keep-alive include="CategoryView"> in App.vue matches this view,
// preserving the infinite-scroll feed + scroll position across a product visit
export default { name: 'CategoryView' }
</script>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'
import { useCatalogStore } from '../stores/catalog'
import { useToastStore } from '../stores/toast'
import PortalBar from '../components/PortalBar.vue'
import CartDrawer from '../components/CartDrawer.vue'
import ProductFeed from '../components/ProductFeed.vue'

const CATS = {
  pantry: { eyebrow: 'home.pantryEyebrow', title: 'home.pantryTitle', desc: 'home.pantryDesc' },
  pottery: { eyebrow: 'home.potteryEyebrow', title: 'home.potteryTitle', desc: 'home.potteryDesc' },
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const catalog = useCatalogStore()
const toast = useToastStore()

const cat = computed(() => route.params.cat)
// last *valid* category we showed. Drives the feed + header so they stay stable
// while the view is kept alive on a product page (where route.params.cat is gone).
const activeCat = ref(CATS[route.params.cat] ? route.params.cat : 'pantry')
const meta = computed(() => CATS[activeCat.value] || CATS.pantry)
const openCart = ref(false)
const scrolled = ref(false)
const type = ref('')
const types = ref([])

function onAdded(p) { toast.show(t('cart.added', { name: p.name })) }
function goCheckout() {
  openCart.value = false
  router.push({ name: 'home', query: { checkout: '1' } })
}
function backToStore() {
  if (window.history.state?.back) router.back()
  else router.push('/')
}

function loadTypes() {
  type.value = ''
  catalog.fetchTypes(activeCat.value).then((t) => (types.value = t)).catch(() => {})
}
watch(cat, (c) => {
  if (!c) return                    // navigated away (e.g. to a product) — keep state for back
  if (!CATS[c]) { router.replace('/'); return } // unknown category → storefront
  activeCat.value = c               // switched to another real category
  loadTypes()
})

function onScroll() { scrolled.value = scrollY > 10 }
onMounted(() => {
  if (!CATS[cat.value]) { router.replace('/'); return }
  loadTypes()
  addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => removeEventListener('scroll', onScroll))
</script>

<style scoped>
.cat-page { min-height: 100vh; background: var(--cream); }
.cat-body { padding: 1.4rem 0 4rem; }
.cat-back { display: inline-flex; align-items: center; gap: .3rem; color: var(--green); font-weight: 700; margin-bottom: 1.2rem; }
.cat-back:hover { color: var(--gold); }
[dir="rtl"] .cat-back svg { transform: scaleX(-1); }
.sec-head { text-align: center; margin-bottom: 1.4rem; }
.type-filter { display: flex; flex-wrap: wrap; gap: .5rem; margin: 0 0 1.6rem; justify-content: center; }
.type-chip {
  padding: .45rem 1.1rem; border-radius: 999px;
  border: 1.5px solid rgba(60,74,39,.22); background: transparent;
  color: var(--green); font-family: inherit; font-size: .9rem; font-weight: 600;
  cursor: pointer; transition: background .15s, color .15s, border-color .15s;
}
.type-chip:hover { border-color: var(--green); }
.type-chip.on { background: var(--green); color: #fff; border-color: var(--green); }
</style>
