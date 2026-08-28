<template>
  <div class="pdp">
    <PortalBar :scrolled="scrolled" search>
      <template #actions>
        <button class="cart-btn" @click="openCart = true" aria-label="cart">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
          <span v-if="cart.count" class="badge">{{ cart.count }}</span>
        </button>
      </template>
    </PortalBar>

    <main class="wrap pdp-body">
      <!-- while /api/products/:id is loading, show a skeleton in the real layout -->
      <div v-if="loading && !product" class="pdp-grid" aria-hidden="true">
        <div class="pdp-gallery">
          <div class="pdp-main sk"></div>
          <div class="pdp-thumbs"><span class="sk sk-thumb"></span><span class="sk sk-thumb"></span><span class="sk sk-thumb"></span></div>
        </div>
        <div class="pdp-info sk-info">
          <span class="sk sk-line" style="width:32%"></span>
          <span class="sk sk-line lg" style="width:72%"></span>
          <span class="sk sk-line" style="width:100%"></span>
          <span class="sk sk-line" style="width:88%"></span>
          <span class="sk sk-line xl" style="width:38%"></span>
          <span class="sk sk-btn"></span>
        </div>
      </div>
      <div v-else-if="!product" class="pdp-missing">
        <p class="a-muted">{{ t('product.notFound') }}</p>
        <RouterLink to="/" class="btn btn-green">{{ t('product.backToStore') }}</RouterLink>
      </div>

      <template v-else>
        <a href="/" class="pdp-back" @click.prevent="backToStore">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M15 6l-6 6 6 6"/></svg>
          {{ t('product.backToStore') }}
        </a>

        <div class="pdp-grid">
          <!-- gallery -->
          <div class="pdp-gallery">
            <div class="pdp-main" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
              <img v-if="images.length" :src="images[idx]" :alt="pname">
              <span v-else class="thumb-empty">{{ t('image.noImage') }}</span>
              <template v-if="images.length > 1">
                <button class="car-nav prev" @click="prev" :aria-label="t('image.prev')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg></button>
                <button class="car-nav next" @click="next" :aria-label="t('image.next')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></button>
              </template>
            </div>
            <div v-if="images.length > 1" class="pdp-thumbs">
              <button v-for="(im, i) in images" :key="i" :class="{ on: i === idx }" @click="idx = i">
                <img :src="im" :alt="`${pname} ${i + 1}`">
              </button>
            </div>
          </div>

          <!-- info + add to cart -->
          <div class="pdp-info">
            <span v-if="ptag" class="eyebrow">{{ ptag }}</span>
            <h1 class="display">{{ pname }}</h1>
            <p class="pdp-desc">{{ pdesc }}</p>
            <div class="pdp-price">
              {{ price }} <span class='dh' role='img' aria-label='درهم'></span>
              <s v-if="onSale" class="was">{{ product.price }} <span class='dh' role='img' aria-label='درهم'></span></s>
              <small>/ {{ punit }}</small>
              <span v-if="onSale" class="save-pill">{{ t('product.saleOff', { n: saleOff }) }}</span>
            </div>

            <!-- in stock / sold out only; the remaining count stays internal -->
            <p v-if="product.stock === 0" class="pdp-stock out">{{ t('product.outOfStock') }}</p>
            <p v-else class="pdp-stock in">{{ t('product.inStock') }}</p>

            <!-- sold out: let the customer ask to be told when it's back, so the
                 visit isn't a dead end -->
            <button v-if="product.stock === 0" class="pdp-notify" :class="{ on: notifyOn }" :disabled="notifyBusy || notifyOn" @click="notifyMe">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 1 0-12 0c0 7-2 8-2 8h16s-2-1-2-8"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
              {{ notifyOn ? t('product.notifyOn') : t('product.notifyMe') }}
            </button>

            <button v-if="auth.isManager" class="pdp-edit" @click="editOpen = true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              {{ t('manager.editProduct') }}
            </button>

            <div class="pdp-buy">
            <div class="pdp-share-wrap">
              <button class="pdp-share" :class="{ on: shareOpen }" @click="toggleShare" :aria-label="t('product.share')" :aria-expanded="shareOpen">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>
                <span>{{ t('product.share') }}</span>
              </button>
              <transition name="v">
                <div v-if="shareOpen" class="share-row" role="menu">
                  <a class="sh sh-wa" :href="shareLinks.whatsapp" target="_blank" rel="noopener" :title="t('product.via.whatsapp')" :aria-label="t('product.via.whatsapp')" @click="shareOpen = false">
                    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.5 14.4c-.3-.15-1.7-.84-1.96-.94-.26-.1-.45-.15-.64.15-.19.29-.74.94-.9 1.13-.17.19-.33.22-.62.07-.29-.15-1.23-.45-2.34-1.44-.86-.77-1.45-1.72-1.62-2.01-.17-.29-.02-.45.13-.6.13-.13.29-.34.44-.51.15-.17.19-.29.29-.48.1-.19.05-.36-.02-.51-.08-.15-.64-1.55-.88-2.12-.23-.55-.47-.48-.64-.49l-.55-.01c-.19 0-.5.07-.76.36-.26.29-1 .98-1 2.38s1.02 2.76 1.17 2.95c.15.19 2.02 3.08 4.9 4.32.68.3 1.22.47 1.64.6.69.22 1.31.19 1.81.12.55-.08 1.7-.69 1.94-1.36.24-.67.24-1.24.17-1.36-.07-.12-.26-.19-.55-.34ZM12 2a10 10 0 0 0-8.53 15.24L2 22l4.87-1.44A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-2.89.85.77-2.82-.19-.29A8.2 8.2 0 1 1 12 20.2Z"/></svg>
                  </a>
                  <a class="sh sh-fb" :href="shareLinks.facebook" target="_blank" rel="noopener" :title="t('product.via.facebook')" :aria-label="t('product.via.facebook')" @click="shareOpen = false">
                    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M22 12a10 10 0 1 0-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.77-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0 0 22 12Z"/></svg>
                  </a>
                  <a class="sh sh-tg" :href="shareLinks.telegram" target="_blank" rel="noopener" :title="t('product.via.telegram')" :aria-label="t('product.via.telegram')" @click="shareOpen = false">
                    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm4.64 6.8-1.56 7.36c-.12.53-.43.66-.86.41l-2.38-1.75-1.15 1.1c-.13.13-.24.24-.48.24l.17-2.43 4.42-3.99c.19-.17-.04-.27-.3-.1L9.4 13.2l-2.35-.73c-.51-.16-.52-.51.11-.76l9.18-3.54c.42-.16.79.1.65.63Z"/></svg>
                  </a>
                  <a class="sh sh-x" :href="shareLinks.x" target="_blank" rel="noopener" :title="t('product.via.x')" :aria-label="t('product.via.x')" @click="shareOpen = false">
                    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.5 3h3l-6.56 7.5L21.75 21h-6.03l-4.72-6.17L5.6 21H2.6l7.02-8.02L2.25 3h6.18l4.27 5.64L17.5 3Zm-1.06 16.2h1.66L7.64 4.71H5.86l10.58 14.49Z"/></svg>
                  </a>
                  <a class="sh sh-em" :href="shareLinks.email" :title="t('product.via.email')" :aria-label="t('product.via.email')" @click="shareOpen = false">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>
                  </a>
                  <button class="sh sh-cp" @click="copyLink" :title="t('product.copyLink')" :aria-label="t('product.copyLink')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
                  </button>
                  <button v-if="canNativeShare" class="sh sh-more" @click="nativeShare" :title="t('product.moreApps')" :aria-label="t('product.moreApps')">
                    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/></svg>
                  </button>
                </div>
              </transition>
              <div v-if="shareOpen" class="share-backdrop" @click="shareOpen = false"></div>
            </div>

            <div class="pdp-actions">
              <WishlistButton :product="product" size="md" label />
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
        </div>

        <!-- more from the same shelf — keeps the visit going instead of ending
             at a single product -->
        <section v-if="related.length" class="pdp-related">
          <h2 class="display">{{ t('product.relatedTitle') }}</h2>
          <div class="rel-row">
            <ProductCard v-for="(p, i) in related" :key="p.id" :product="p" :index="i" @added="onRelatedAdded" />
          </div>
        </section>
      </template>
    </main>

    <CartDrawer :open="openCart" @close="openCart = false" @checkout="goCheckout" />
    <Dialog :open="editOpen" :title="t('manager.editProduct')" max-width="520px" @close="editOpen = false">
      <ProductEditor v-if="editOpen && product" :product="product" @saved="onEdited" />
    </Dialog>
    <transition name="v"><div class="toast" v-if="toast"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>{{ toast }}</div></transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useHead } from '@unhead/vue'
import { useCatalogStore } from '../stores/catalog'
import { useCartStore } from '../stores/cart'
import { useAuthStore } from '../stores/auth'
import { api } from '../services/api'
import { pName, pDesc, pUnit, pTag, pPrice, pIsOnSale, pSaleOff } from '../utils/product'
import PortalBar from '../components/PortalBar.vue'
import CartDrawer from '../components/CartDrawer.vue'
import Dialog from '../components/Dialog.vue'
import ProductEditor from '../components/ProductEditor.vue'
import ProductCard from '../components/ProductCard.vue'
import WishlistButton from '../components/WishlistButton.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const catalog = useCatalogStore()
const cart = useCartStore()
const auth = useAuthStore()

const openCart = ref(false)
const editOpen = ref(false)
const toast = ref('')
const idx = ref(0)
const scrolled = ref(false)
const loading = ref(false)

const product = computed(() => catalog.products.find((p) => p.id === route.params.id))
const images = computed(() => {
  const imgs = product.value?.images
  if (Array.isArray(imgs) && imgs.length) return imgs
  return product.value?.image_url ? [product.value.image_url] : []
})

// product copy in the active language (falls back to Arabic when untranslated)
const pname = computed(() => pName(product.value))
const pdesc = computed(() => pDesc(product.value))
const punit = computed(() => pUnit(product.value))
const ptag = computed(() => pTag(product.value))
const price = computed(() => pPrice(product.value))
const onSale = computed(() => pIsOnSale(product.value))
const saleOff = computed(() => pSaleOff(product.value))

// Per-product <head> for SEO. Reactive to the loaded product, so it updates once
// the detail loads. Runs client-side (product pages aren't prerendered); this gives
// JS-capable crawlers a unique title/description per product.
const brand = 'دكّان كنعان'
const origin = computed(() => (typeof window !== 'undefined' ? window.location.origin : ''))
const canonicalUrl = computed(() => (origin.value ? `${origin.value}/product/${route.params.id}` : ''))

// Absolute URL for the primary image. Product photos are stored as files under
// /media now, so unlike the old base64 data-URLs they work as an og:image.
const absoluteImage = computed(() => {
  const src = product.value?.image_url || images.value[0] || ''
  if (!src || src.startsWith('data:')) return ''
  return /^https?:\/\//.test(src) ? src : origin.value + src
})

// Product structured data. This is what lets Google show the price and an
// in-stock badge next to the result instead of a plain blue link. Deliberately
// carries no rating — we don't have real reviews yet, and inventing them is both
// against Google's policy and a lie to the customer.
const jsonLd = computed(() => {
  const p = product.value
  if (!p) return null
  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: pname.value,
    description: pdesc.value,
    sku: p.id,
    ...(absoluteImage.value ? { image: [absoluteImage.value] } : {}),
    brand: { '@type': 'Brand', name: brand },
    offers: {
      '@type': 'Offer',
      url: canonicalUrl.value,
      price: pPrice(p),
      priceCurrency: 'AED',
      availability: p.stock > 0 ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
      itemCondition: 'https://schema.org/NewCondition',
    },
  }
})

useHead({
  title: () => (pname.value ? `${pname.value} — ${brand}` : brand),
  link: [{ rel: 'canonical', href: () => canonicalUrl.value }],
  meta: [
    { name: 'description', content: () => pdesc.value },
    { property: 'og:type', content: 'product' },
    { property: 'og:title', content: () => pname.value || brand },
    { property: 'og:description', content: () => pdesc.value },
    { property: 'og:url', content: () => canonicalUrl.value },
    { property: 'og:image', content: () => absoluteImage.value },
  ],
  script: [{
    type: 'application/ld+json',
    innerHTML: () => (jsonLd.value ? JSON.stringify(jsonLd.value) : ''),
  }],
})

function prev() { idx.value = (idx.value - 1 + images.value.length) % images.value.length }
function next() { idx.value = (idx.value + 1) % images.value.length }

// swipe the gallery on touch devices (only when there's more than one image)
let touchX = null
function onTouchStart(e) { touchX = e.changedTouches[0].clientX }
function onTouchEnd(e) {
  if (touchX === null || images.value.length < 2) return
  const dx = e.changedTouches[0].clientX - touchX
  touchX = null
  if (Math.abs(dx) < 40) return   // ignore taps / tiny drags
  dx < 0 ? next() : prev()        // swipe left → next, right → previous
}

// --- share menu -----------------------------------------------------------
// A custom menu (not just the native sheet) so the options show on every
// browser, desktop included: WhatsApp / Facebook / Telegram / X / Email / Copy,
// plus a "More apps…" entry backed by the native share sheet where available.
const shareOpen = ref(false)
const canNativeShare = ref(false)

const shareUrl = computed(() => (typeof window !== 'undefined' ? window.location.href : ''))
const shareMsg = computed(() => `${t('product.shareText')} — ${pname.value}`)
const shareLinks = computed(() => {
  const u = encodeURIComponent(shareUrl.value)
  const txt = encodeURIComponent(shareMsg.value)
  const full = encodeURIComponent(`${shareMsg.value}\n${shareUrl.value}`)
  return {
    whatsapp: `https://wa.me/?text=${full}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
    telegram: `https://t.me/share/url?url=${u}&text=${txt}`,
    x: `https://twitter.com/intent/tweet?text=${txt}&url=${u}`,
    email: `mailto:?subject=${encodeURIComponent(pname.value)}&body=${full}`,
  }
})

function toggleShare() { shareOpen.value = !shareOpen.value }
async function copyLink() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    toast.value = t('product.linkCopied')
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (toast.value = ''), 2000)
  } catch { /* clipboard blocked */ }
  shareOpen.value = false
}
async function nativeShare() {
  shareOpen.value = false
  try { await navigator.share({ title: pname.value, text: shareMsg.value, url: shareUrl.value }) } catch { /* dismissed */ }
}

let toastTimer
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2200)
}
function onEdited() {
  editOpen.value = false
  showToast(t('manager.toastSaved'))
}
function add() {
  if (cart.qty(product.value.id) >= product.value.stock) return
  cart.add(product.value)
  toast.value = t('cart.added', { name: pname.value })
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2200)
}

// go back so the storefront's scroll position is restored; if the customer
// deep-linked straight here (no in-app history), just go to the store.
function backToStore() {
  if (window.history.state?.back) router.back()
  else router.push('/')
}

// checkout lives on the home page; route there and let it open the modal
function goCheckout() {
  openCart.value = false
  router.push({ name: 'home', query: { checkout: '1' } })
}

function onScroll() { scrolled.value = scrollY > 10 }

// --- related products -----------------------------------------------------
const related = ref([])

async function loadRelated(id) {
  related.value = []
  try {
    const { products } = await api(`/products/${id}/related`)
    related.value = products || []
  } catch { /* a missing suggestions row isn't worth interrupting the page for */ }
}
function onRelatedAdded(p) { showToast(t('cart.added', { name: pName(p) })) }

// --- "tell me when it's back" ---------------------------------------------
const notifyOn = ref(false)
const notifyBusy = ref(false)

async function loadStockAlert(id) {
  notifyOn.value = false
  if (!auth.isAuthenticated || product.value?.stock !== 0) return
  try {
    const { subscribed } = await api(`/products/${id}/stock-alert`)
    notifyOn.value = subscribed
  } catch { /* button just shows as un-subscribed */ }
}

async function notifyMe() {
  if (!auth.isAuthenticated) {
    showToast(t('product.notifyLogin'))
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  notifyBusy.value = true
  try {
    await api(`/products/${route.params.id}/stock-alert`, { method: 'POST' })
    notifyOn.value = true
    showToast(t('product.notifyDone'))
  } catch (e) {
    showToast(e.message)
  } finally {
    notifyBusy.value = false
  }
}

// Load the full-quality product (with its gallery) for the detail page. Only
// block on the loader when there's nothing to show yet — if the product came
// from a storefront feed it renders instantly while the gallery refreshes.
async function load(id) {
  idx.value = 0
  loading.value = !product.value
  try {
    await catalog.fetchOne(id)
  } catch {
    if (!catalog.products.length) { try { await catalog.fetch() } catch { /* leave as not-found */ } }
  } finally {
    loading.value = false
  }
  loadRelated(id)
  loadStockAlert(id)
}

// A related-product card routes to this same view, so the component is reused
// and onMounted won't fire again — the id has to be watched or the page would
// keep showing the previous product's gallery.
watch(() => route.params.id, (id) => { if (id) load(id) })

onMounted(() => {
  addEventListener('scroll', onScroll, { passive: true })
  canNativeShare.value = typeof navigator !== 'undefined' && !!navigator.share
  load(route.params.id)
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
.pdp-price .was { font-size: 1.2rem; color: var(--muted); opacity: .8; margin-inline-start: .55rem; text-decoration-thickness: 2px; }
.pdp-price .save-pill { font-size: .8rem; padding: .32rem .7rem; vertical-align: .38rem; }
.pdp-stock { font-size: .9rem; font-weight: 700; margin-bottom: 1.2rem; }
.pdp-stock.in { color: var(--green-soft); }
.pdp-stock.low { color: var(--gold); }
.pdp-stock.out { color: var(--red); }
/* Add + Share share one line; Add first (order:1), Share after (order:2) */
.pdp-buy { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; margin: .4rem 0 1.2rem; }
.pdp-buy .pdp-actions { order: 1; }
.pdp-buy .pdp-share-wrap { order: 2; }
.pdp-share-wrap { position: relative; z-index: 41; display: inline-flex; }
.pdp-share {
  display: inline-flex; align-items: center; gap: .5rem;
  padding: .6rem 1.1rem; border-radius: 999px;
  border: 2px solid var(--gold); background: transparent;
  color: var(--terra-deep); font-family: inherit; font-size: .9rem; font-weight: 700;
  cursor: pointer; transition: transform .2s, background .2s, color .2s;
}
.pdp-share:hover, .pdp-share.on { background: var(--gold); color: var(--cream); transform: translateY(-2px); }
.pdp-share svg { width: 18px; height: 18px; }

.share-backdrop { position: fixed; inset: 0; z-index: 40; }
/* row of round brand buttons — drops below the Share button as a popover so it
   never pushes the Add button around */
.share-row {
  position: absolute; z-index: 41; top: calc(100% + .5rem); inset-inline-start: 0;
  display: inline-flex; align-items: center; gap: .45rem;
  padding: .5rem; background: #fff;
  border: 1px solid rgba(60,74,39,.14); border-radius: 999px;
  box-shadow: 0 16px 34px -14px rgba(0,0,0,.4);
}
.sh {
  width: 42px; height: 42px; border-radius: 999px; flex: 0 0 auto;
  display: grid; place-items: center; border: none; cursor: pointer;
  color: #fff; box-shadow: 0 12px 24px -14px rgba(0,0,0,.7);
  transition: transform .2s, filter .2s;
}
.sh:hover { transform: translateY(-2px); filter: brightness(1.06); }
.sh svg { width: 21px; height: 21px; }
.sh-wa { background: #25d366; }
.sh-fb { background: #1877f2; }
.sh-tg { background: #229ed9; }
.sh-x  { background: #111; }
.sh-em { background: var(--green); }
.sh-cp { background: var(--gold); }
.sh-more { background: var(--terra-deep, #7a3b2e); }
/* manager-only quick edit on the product page */
.pdp-edit {
  display: inline-flex; align-items: center; gap: .45rem;
  margin-bottom: 1rem; padding: .5rem 1rem; border-radius: 999px;
  border: 1.5px dashed var(--gold); background: transparent;
  color: var(--terra-deep); font-family: inherit; font-size: .88rem; font-weight: 700;
  cursor: pointer; transition: background .2s, color .2s;
}
.pdp-edit:hover { background: var(--gold); color: var(--cream); }
.pdp-edit svg { width: 16px; height: 16px; }
.pdp-actions { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; }
.stepper.big { font-size: 1.1rem; }
.stepper.big button { width: 42px; height: 42px; }

/* "tell me when it's back" — shown only while sold out */
.pdp-notify {
  display: inline-flex; align-items: center; gap: .45rem;
  margin-bottom: 1rem; padding: .55rem 1.1rem; border-radius: 999px;
  border: 1.5px solid var(--green); background: transparent;
  color: var(--green); font-family: inherit; font-size: .88rem; font-weight: 700;
  cursor: pointer; transition: background .2s, color .2s;
}
.pdp-notify:hover:not(:disabled) { background: var(--green); color: var(--cream); }
.pdp-notify.on { border-style: dashed; opacity: .8; cursor: default; }
.pdp-notify:disabled { cursor: default; }
.pdp-notify svg { width: 16px; height: 16px; }

/* related products */
.pdp-related { margin-top: 3.4rem; }
.pdp-related h2 {
  font-family: "Amiri", serif; font-size: clamp(1.4rem, 3vw, 2rem);
  color: var(--green); margin-bottom: 1.2rem;
}
/* A scroll-snapping row on narrow screens, a plain grid once there's room. Cards
   keep a fixed width while scrolling so they don't squash to nothing. */
.rel-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(212px, 1fr)); gap: 1.2rem; }

@media (max-width: 760px) {
  .pdp-grid { grid-template-columns: 1fr; gap: 1.4rem; }
  .rel-row {
    display: flex; overflow-x: auto; scroll-snap-type: x mandatory;
    gap: 1rem; padding-bottom: .6rem; margin-inline: -1rem; padding-inline: 1rem;
    scrollbar-width: none;
  }
  .rel-row::-webkit-scrollbar { display: none; }
  .rel-row > * { flex: 0 0 62%; scroll-snap-align: start; }
}

/* loading skeleton — mirrors the real product layout so nothing is empty */
.sk {
  position: relative; overflow: hidden;
  background: var(--cream-2, rgba(60,74,39,.08)); border-radius: 12px;
}
.sk::after {
  content: ""; position: absolute; inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.55), transparent);
  animation: skshimmer 1.3s infinite;
}
[dir="rtl"] .sk::after { animation-name: skshimmer-rtl; }
@keyframes skshimmer { 100% { transform: translateX(100%); } }
@keyframes skshimmer-rtl { 100% { transform: translateX(-100%); } }
.sk-info { display: grid; gap: .8rem; align-content: start; }
.sk-line { height: 1rem; border-radius: 8px; }
.sk-line.lg { height: 2.2rem; }
.sk-line.xl { height: 2.6rem; margin-top: .4rem; }
.sk-thumb { width: 68px; height: 68px; border-radius: 12px; }
.sk-btn { height: 46px; width: 180px; border-radius: 999px; margin-top: .6rem; }
</style>
