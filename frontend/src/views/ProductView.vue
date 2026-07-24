<template>
  <div class="pdp">
    <PortalBar :scrolled="scrolled">
      <template #actions>
        <button class="cart-btn" @click="openCart = true" aria-label="cart">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
          <span v-if="cart.count" class="badge">{{ cart.count }}</span>
        </button>
      </template>
    </PortalBar>

    <main class="wrap pdp-body">
      <p v-if="catalog.loading && !product" class="a-muted" style="text-align:center">{{ t('common.loading') }}</p>
      <div v-else-if="!product" class="pdp-missing">
        <p class="a-muted">{{ t('product.notFound') }}</p>
        <RouterLink to="/" class="btn btn-green">{{ t('product.backToStore') }}</RouterLink>
      </div>

      <template v-else>
        <RouterLink to="/" class="pdp-back">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M15 6l-6 6 6 6"/></svg>
          {{ t('product.backToStore') }}
        </RouterLink>

        <div class="pdp-grid">
          <!-- gallery -->
          <div class="pdp-gallery">
            <div class="pdp-main">
              <img v-if="images.length" :src="images[idx]" :alt="product.name">
              <span v-else class="thumb-empty">{{ t('image.noImage') }}</span>
              <template v-if="images.length > 1">
                <button class="car-nav prev" @click="prev" :aria-label="t('image.prev')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg></button>
                <button class="car-nav next" @click="next" :aria-label="t('image.next')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></button>
              </template>
            </div>
            <div v-if="images.length > 1" class="pdp-thumbs">
              <button v-for="(im, i) in images" :key="i" :class="{ on: i === idx }" @click="idx = i">
                <img :src="im" :alt="`${product.name} ${i + 1}`">
              </button>
            </div>
          </div>

          <!-- info + add to cart -->
          <div class="pdp-info">
            <span v-if="product.tag" class="eyebrow">{{ product.tag }}</span>
            <h1 class="display">{{ product.name }}</h1>
            <p class="pdp-desc">{{ product.description }}</p>
            <div class="pdp-price">{{ product.price }} <span class='dh' role='img' aria-label='درهم'></span> <small>/ {{ product.unit }}</small></div>

            <p v-if="product.stock === 0" class="pdp-stock out">{{ t('product.outOfStock') }}</p>
            <p v-else-if="product.stock <= 5" class="pdp-stock low">{{ t('product.fewLeft', { n: product.stock }) }}</p>
            <p v-else class="pdp-stock in">{{ t('product.inStock') }}</p>

            <div class="pdp-actions">
              <span v-if="product.stock === 0" class="btn btn-green" style="opacity:.5;pointer-events:none">{{ t('product.outOfStock') }}</span>
              <button v-else-if="!cart.qty(product.id)" class="btn btn-green" @click="add">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>{{ t('product.add') }}
              </button>
              <span v-else class="stepper big">
                <button @click="cart.dec(product.id)" aria-label="إنقاص">−</button>
                <span>{{ cart.qty(product.id) }}</span>
                <button @click="add" aria-label="زيادة" :disabled="cart.qty(product.id) >= product.stock">+</button>
              </span>
              <button v-if="cart.count" class="btn btn-gold" @click="openCart = true">{{ t('product.viewCart') }}</button>
            </div>
          </div>
        </div>
      </template>
    </main>

    <CartDrawer :open="openCart" @close="openCart = false" @checkout="goCheckout" />
    <transition name="v"><div class="toast" v-if="toast"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>{{ toast }}</div></transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCatalogStore } from '../stores/catalog'
import { useCartStore } from '../stores/cart'
import PortalBar from '../components/PortalBar.vue'
import CartDrawer from '../components/CartDrawer.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const catalog = useCatalogStore()
const cart = useCartStore()

const openCart = ref(false)
const toast = ref('')
const idx = ref(0)
const scrolled = ref(false)

const product = computed(() => catalog.products.find((p) => p.id === route.params.id))
const images = computed(() => {
  const imgs = product.value?.images
  if (Array.isArray(imgs) && imgs.length) return imgs
  return product.value?.image_url ? [product.value.image_url] : []
})

function prev() { idx.value = (idx.value - 1 + images.value.length) % images.value.length }
function next() { idx.value = (idx.value + 1) % images.value.length }

let toastTimer
function add() {
  if (cart.qty(product.value.id) >= product.value.stock) return
  cart.add(product.value)
  toast.value = t('cart.added', { name: product.value.name })
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2200)
}

// checkout lives on the home page; route there and let it open the modal
function goCheckout() {
  openCart.value = false
  router.push({ name: 'home', query: { checkout: '1' } })
}

function onScroll() { scrolled.value = scrollY > 10 }

onMounted(() => {
  if (!catalog.products.length) catalog.fetch()
  addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => removeEventListener('scroll', onScroll))
</script>

<style scoped>
.pdp { min-height: 100vh; background: var(--cream); }
.pdp-body { padding: 1.6rem 0 4rem; }
.pdp-missing { text-align: center; padding: 4rem 0; display: grid; gap: 1.2rem; place-items: center; }
.pdp-back { display: inline-flex; align-items: center; gap: .3rem; color: var(--green); font-weight: 700; margin-bottom: 1.2rem; }
.pdp-back:hover { color: var(--gold); }
/* the chevron points "back": left in LTR, right in RTL (Arabic) */
[dir="rtl"] .pdp-back svg { transform: scaleX(-1); }
.pdp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2.2rem; align-items: start; }

.pdp-main {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 20px;
  overflow: hidden;
  background: radial-gradient(circle at 50% 35%, var(--cream), var(--cream-2));
  border: 1px solid rgba(60, 74, 39, .12);
}
.pdp-main img { width: 100%; height: 100%; object-fit: contain; }
.thumb-empty { position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); }
.pdp-thumbs { display: flex; gap: .5rem; margin-top: .7rem; flex-wrap: wrap; }
.pdp-thumbs button {
  width: 68px; height: 68px; border-radius: 12px; overflow: hidden;
  border: 2px solid transparent; background: var(--cream-2); flex: 0 0 auto;
}
.pdp-thumbs button.on { border-color: var(--green); }
.pdp-thumbs img { width: 100%; height: 100%; object-fit: contain; }

.car-nav {
  position: absolute; top: 50%; transform: translateY(-50%);
  width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
  background: rgba(255,255,255,.9); color: var(--green); box-shadow: 0 4px 12px -4px rgba(0,0,0,.4);
}
.car-nav svg { width: 20px; height: 20px; }
.car-nav.prev { inset-inline-start: 10px; }
.car-nav.next { inset-inline-end: 10px; }
.car-nav:hover { background: #fff; }

.pdp-info .eyebrow { margin-bottom: .5rem; }
.pdp-info h1 { font-size: clamp(1.8rem, 4vw, 2.6rem); color: var(--green); line-height: 1.2; margin: .2rem 0 .6rem; }
.pdp-desc { color: var(--ink); font-size: 1.05rem; margin-bottom: 1.2rem; }
.pdp-price { font-family: "Amiri", serif; font-size: 2rem; color: var(--terra-deep); margin-bottom: .5rem; }
.pdp-price small { font-size: 1rem; color: var(--muted); }
.pdp-stock { font-size: .9rem; font-weight: 700; margin-bottom: 1.2rem; }
.pdp-stock.in { color: var(--green-soft); }
.pdp-stock.low { color: var(--gold); }
.pdp-stock.out { color: var(--red); }
.pdp-actions { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; }
.stepper.big { font-size: 1.1rem; }
.stepper.big button { width: 42px; height: 42px; }

@media (max-width: 760px) {
  .pdp-grid { grid-template-columns: 1fr; gap: 1.4rem; }
}
</style>
