<template>
  <PortalBar :scrolled="scrolled">
    <nav class="tabs store-nav" aria-label="nav">
      <a href="#home" :class="{ active: activeSection === 'home' }">{{ t('nav.home') }}</a><a href="#pantry" :class="{ active: activeSection === 'pantry' }">{{ t('nav.pantry') }}</a><a href="#pottery" :class="{ active: activeSection === 'pottery' }">{{ t('nav.pottery') }}</a><a href="#story" :class="{ active: activeSection === 'story' }">{{ t('nav.story') }}</a><a href="#contact" :class="{ active: activeSection === 'contact' }">{{ t('nav.contact') }}</a>
    </nav>
    <template #actions>
      <button class="cart-btn" @click="openCart = true" aria-label="cart">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
        <span v-if="cart.count" class="badge" :class="{ pop: badgePop }">{{ ar(cart.count) }}</span>
      </button>
      <button class="burger" @click="mobileMenu = !mobileMenu" aria-label="menu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
    </template>
  </PortalBar>
  <!-- mobile nav sidebar -->
  <transition name="v"><div v-if="mobileMenu" class="mm-overlay" @click="mobileMenu = false"></div></transition>
  <aside class="mobile-menu" :class="{ show: mobileMenu }" aria-label="القائمة">
    <div class="mm-head">
      <span class="mm-brand"><span class="g">دكّان</span> كنعان</span>
      <button class="mm-close" @click="mobileMenu = false" aria-label="إغلاق"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
    </div>
    <nav class="mm-links">
      <a href="#home" :class="{ active: activeSection === 'home' }" @click="mobileMenu = false">{{ t('nav.home') }}</a>
      <a href="#pantry" :class="{ active: activeSection === 'pantry' }" @click="mobileMenu = false">{{ t('nav.pantry') }}</a>
      <a href="#pottery" :class="{ active: activeSection === 'pottery' }" @click="mobileMenu = false">{{ t('nav.pottery') }}</a>
      <a href="#story" :class="{ active: activeSection === 'story' }" @click="mobileMenu = false">{{ t('nav.story') }}</a>
      <a href="#contact" :class="{ active: activeSection === 'contact' }" @click="mobileMenu = false">{{ t('nav.contact') }}</a>
      <RouterLink v-if="auth.isAuthenticated" to="/account" @click="mobileMenu = false">{{ t('nav.account') }}</RouterLink>
      <RouterLink v-else to="/login" @click="mobileMenu = false">{{ t('auth.loginTitle') }}</RouterLink>
    </nav>
  </aside>

  <!-- product search — sticky under the nav; auto-hides on scroll down, returns on scroll up / at top -->
  <div class="search-bar" :class="{ hidden: searchHidden }">
    <div class="search-inner">
      <svg class="search-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>
      <input class="search-input" v-model="searchQuery" :placeholder="t('search.placeholder')" type="search" enterkeyhint="search" aria-label="search">
      <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''" :aria-label="t('search.clear')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
    </div>
  </div>

  <!-- search results -->
  <section v-if="searching" class="search-results">
    <div class="wrap">
      <div class="sec-head"><h2 class="display">{{ t('search.resultsTitle') }}</h2><p>{{ t('search.resultsFor', { q: activeQuery }) }}</p></div>
      <ProductFeed :q="activeQuery" :empty-text="t('search.noResults')" @added="onAdded" />
    </div>
  </section>

  <template v-else>
  <!-- hero -->
  <section class="hero" id="home">
    <img class="hero-img" src="/images/hero.jpg" alt="دكّان كنعان — مونة وخزف فلسطيني" /><a class="scroll-cue" href="#pantry" aria-label="استكشف المتجر"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></a>
    <div class="cta">
      <a href="#pantry" class="btn btn-green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-12L6 6Z"/><path d="M6 6 5 3H2"/></svg>{{ t('hero.shopPantry') }}</a>
      <a href="#pottery" class="btn btn-gold">{{ t('hero.discoverPottery') }}</a>
    </div>
  </section>

  <!-- categories -->
  <div class="cats">
    <div class="wrap row">
      <a class="cat" href="#pantry"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3h4v3l2 2v12a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V8l2-2Z"/><path d="M8 12h8"/></svg>{{ t('cats.oil') }}</a>
      <a class="cat" href="#pantry"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21c-1-7 2-12 8-14-1 7-3 12-8 14Z"/><path d="M12 21c1-6-1-10-6-12 1 6 2 9 6 12Z"/></svg>{{ t('cats.zaatar') }}</a>
      <a class="cat" href="#pantry"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14 14 6l6 4-2 8H6Z"/><circle cx="10" cy="13" r="1"/><circle cx="14" cy="14" r="1"/></svg>{{ t('cats.cheese') }}</a>
      <a class="cat" href="#pantry"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6l-1 3 2 3v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V9l2-3Z"/><path d="M8 13h8"/></svg>{{ t('cats.dairy') }}</a>
      <a class="cat" href="#pottery"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6l-1 4c3 1 5 4 5 8s-3 6-7 6-7-2-7-6 2-7 5-8Z"/></svg>{{ t('cats.ceramics') }}</a>
    </div>
  </div>

  <!-- values -->
  <div class="values"><div class="wrap row">
    <button class="value reveal" v-for="v in values" :key="v.id || v.t" @click="onValueClick(v)"><span class="ic" v-html="v.icon"></span><div><b>{{ v.t }}</b><span>{{ v.d }}</span></div><span v-if="auth.isManager && v.id" class="v-edit" :title="t('manager.vcEditHint')" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></span></button>
  </div></div>

  <!-- pantry -->
  <section id="pantry">
    <div class="wrap">
      <div class="sec-head reveal"><span class="eyebrow">{{ t('home.pantryEyebrow') }}</span><h2 class="display">{{ t('home.pantryTitle') }}</h2><p>{{ t('home.pantryDesc') }}</p></div>
      <div v-if="pantryTypes.length" class="type-filter">
        <button class="type-chip" :class="{ on: !pantryType }" @click="pantryType = ''">{{ t('home.allTypes') }}</button>
        <button v-for="ty in pantryTypes" :key="ty" class="type-chip" :class="{ on: pantryType === ty }" @click="pantryType = ty">{{ ty }}</button>
      </div>
      <ProductFeed ref="pantryFeed" category="pantry" :type="pantryType" @added="onAdded" />
    </div>
  </section>

  <!-- pottery -->
  <section class="pottery" id="pottery">
    <div class="wrap">
      <div class="sec-head reveal"><span class="eyebrow">{{ t('home.potteryEyebrow') }}</span><h2 class="display">{{ t('home.potteryTitle') }}</h2><p>{{ t('home.potteryDesc') }}</p></div>
      <div v-if="potteryTypes.length" class="type-filter">
        <button class="type-chip" :class="{ on: !potteryType }" @click="potteryType = ''">{{ t('home.allTypes') }}</button>
        <button v-for="ty in potteryTypes" :key="ty" class="type-chip" :class="{ on: potteryType === ty }" @click="potteryType = ty">{{ ty }}</button>
      </div>
      <ProductFeed ref="potteryFeed" category="pottery" :type="potteryType" @added="onAdded" />
    </div>
  </section>

  <!-- story -->
  <section class="story" id="story">
    <div class="wrap inner">
      <div class="reveal">
        <span class="eyebrow">{{ t('home.storyEyebrow') }}</span>
        <blockquote class="display">{{ t('home.storyQuote') }}</blockquote>
        <p>{{ t('home.storyText') }}</p>
      </div>
      <div class="pic reveal"><img src="/images/tatreez.jpg" alt="قبة الصخرة"></div>
    </div>
  </section>
  </template>

  <footer class="site" id="contact">
    <div class="band" aria-hidden="true"></div>
    <div class="wrap fcols">
      <div class="about"><div class="name display"><span class="g">دكّان</span> كنعان</div><p>{{ t('footer.about') }}</p></div>
      <div><h5>{{ t('footer.shop') }}</h5><a href="#pantry">{{ t('nav.pantry') }}</a><a href="#pottery">{{ t('nav.pottery') }}</a><a href="#pantry">{{ t('footer.harvest') }}</a><a href="#pantry">{{ t('footer.gifts') }}</a></div>
      <div><h5>{{ t('footer.links') }}</h5><a href="#story">{{ t('nav.story') }}</a><a href="#contact">{{ t('footer.contactUs') }}</a><RouterLink to="/account">{{ t('nav.account') }}</RouterLink><a href="#">{{ t('footer.faq') }}</a></div>
      <div><h5>{{ t('footer.contact') }}</h5>
        <a href="https://wa.me/971522981187" target="_blank" rel="noopener">{{ t('footer.whatsapp') }}: <span dir="ltr">+971 52 298 1187</span></a>
        <a href="mailto:mmn00@hotmail.com">mmn00@hotmail.com</a>
        <a href="https://www.instagram.com/dukkan_kanaan" target="_blank" rel="noopener">{{ t('footer.instagram') }} @dukkan_kanaan</a>
        <a class="ig-qr" href="https://www.instagram.com/dukkan_kanaan" target="_blank" rel="noopener" :aria-label="t('footer.followQr')">
          <img src="/images/instagram-qr.svg" alt="Instagram QR">
          <span>{{ t('footer.followQr') }}</span>
        </a>
      </div>
    </div>
    <div class="copy">{{ t('footer.copy') }}</div>
  </footer>

  <!-- basket sidebar -->
  <CartDrawer :open="openCart" @close="openCart = false" @checkout="openCheckout" />

  <!-- value modal -->
  <transition name="v">
    <div class="modal-overlay" v-if="modal" @click.self="modal = null">
      <div class="modal">
        <button class="m-close" @click="modal = null" aria-label="إغلاق"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
        <span class="m-ic" v-html="modal.icon"></span>
        <h3 class="display">{{ modal.t }}</h3>
        <p>{{ modal.more }}</p>
        <a v-if="modal.link" :href="modal.link" class="btn btn-green" @click="modal = null">{{ modal.linkLabel }}</a>
      </div>
    </div>
  </transition>

  <!-- edit value card (managers only) -->
  <transition name="v">
    <div class="modal-overlay" v-if="editingValue" @click.self="editingValue = null">
      <div class="co" style="max-width:560px">
        <button @click="editingValue = null" aria-label="إغلاق" style="position:absolute;top:.8rem;inset-inline-start:.8rem;width:34px;height:34px;border-radius:10px;background:var(--cream-2);color:var(--green);display:grid;place-items:center"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
        <h3 style="font-family:'Amiri',serif;font-size:1.6rem;color:var(--green);text-align:center;margin-bottom:.8rem">{{ t('manager.vcEditTitle') }}</h3>
        <label class="co-l">{{ t('manager.vcImage') }}</label>
        <ImagePicker v-model="evImages" />
        <div class="grid2">
          <div><label class="co-l">{{ t('manager.vcTitle') }} (ع)</label><input class="a-input" v-model.trim="editingValue.title_ar"></div>
          <div><label class="co-l">{{ t('manager.vcTitle') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="editingValue.title_en"></div>
        </div>
        <div class="grid2">
          <div><label class="co-l">{{ t('manager.vcDesc') }} (ع)</label><input class="a-input" v-model.trim="editingValue.desc_ar"></div>
          <div><label class="co-l">{{ t('manager.vcDesc') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="editingValue.desc_en"></div>
        </div>
        <label class="co-l">{{ t('manager.vcMore') }} (ع)</label>
        <textarea class="a-input" rows="3" v-model.trim="editingValue.more_ar"></textarea>
        <label class="co-l">{{ t('manager.vcMore') }} (EN)</label>
        <textarea class="a-input" rows="3" dir="ltr" v-model.trim="editingValue.more_en"></textarea>
        <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="evBusy" @click="saveValue">{{ evBusy ? '…' : t('manager.save') }}</button>
      </div>
    </div>
  </transition>

  <!-- checkout modal -->
  <transition name="v">
  <div class="modal-overlay" v-if="checkoutOpen" @click.self="checkoutOpen = false">
    <div class="co">
      <button @click="checkoutOpen = false" aria-label="إغلاق" style="position:absolute;top:.8rem;inset-inline-start:.8rem;width:34px;height:34px;border-radius:10px;background:var(--cream-2);color:var(--green);display:grid;place-items:center"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
      <h3 style="font-family:'Amiri',serif;font-size:1.7rem;color:var(--green);text-align:center;margin-bottom:.2rem">{{ t('checkout.title') }}</h3>
      <p class="a-muted" style="text-align:center;margin-bottom:.6rem">{{ t('checkout.subtitle', { count: ar(cart.count), total: ar(cart.total) }) }}</p>

      <!-- saved addresses for logged-in customers -->
      <div v-if="auth.isAuthenticated && addresses.addresses.length && !newAddress" style="margin-bottom:.8rem">
        <label class="co-l">{{ t('checkout.chooseAddress') }}</label>
        <label v-for="a in addresses.addresses" :key="a.id" class="addr-pick" :class="{ on: selectedAddressId === a.id }">
          <input type="radio" :value="a.id" v-model="selectedAddressId" style="display:none">
          <b>{{ a.label || '—' }}</b> — {{ t('account.addrLine', { city: a.city, street: a.street, house: a.house }) }}
          <span v-if="a.notes" class="a-muted"> ({{ a.notes }})</span>
        </label>
        <button class="a-btn" style="margin-top:.5rem;background:var(--cream-2);color:var(--green)" @click="newAddress = true">{{ t('checkout.newAddress') }}</button>
      </div>

      <template v-else>
        <p v-if="!auth.isAuthenticated" class="a-muted" style="margin-bottom:.6rem;font-size:.82rem">
          <RouterLink to="/login" style="color:var(--green);text-decoration:underline">{{ t('checkout.loginWord') }}</RouterLink> {{ t('checkout.loginPrompt') }}
        </p>
        <label class="co-l">{{ t('checkout.fullName') }} *</label>
        <input class="a-input" v-model.trim="co.name">
        <label class="co-l">{{ t('checkout.phone') }} *</label>
        <input class="a-input" v-model.trim="co.phone" type="tel" inputmode="tel" dir="ltr" placeholder="050 123 4567">
        <div class="grid2">
          <div><label class="co-l">{{ t('checkout.city') }} *</label>
            <select class="a-input" v-model="co.city">
              <option value="" disabled>{{ t('checkout.cityPick') }}</option>
              <option v-for="e in EMIRATES" :key="e.value" :value="e.value">{{ locale === 'ar' ? e.value : e.en }}</option>
            </select>
          </div>
          <div><label class="co-l">{{ t('checkout.street') }} *</label><input class="a-input" v-model.trim="co.street"></div>
        </div>
        <div class="grid2">
          <div><label class="co-l">{{ t('checkout.house') }} *</label><input class="a-input" v-model.trim="co.house"></div>
          <div><label class="co-l">{{ t('checkout.landmark') }}</label><input class="a-input" v-model.trim="co.notes"></div>
        </div>
        <label v-if="auth.isAuthenticated" style="display:flex;gap:.4rem;align-items:center;margin-top:.6rem;font-size:.85rem;color:var(--ink)">
          <input type="checkbox" v-model="saveAddress"> {{ t('checkout.saveAddress') }}
        </label>
        <button v-if="auth.isAuthenticated && addresses.addresses.length" class="a-btn" style="margin-top:.5rem;background:var(--cream-2);color:var(--green)" @click="newAddress = false">{{ t('checkout.savedAddresses') }}</button>
      </template>

      <label class="co-l" style="margin-top:.8rem">{{ t('checkout.promo') }}</label>
      <div style="display:flex;gap:.5rem">
        <input class="a-input" v-model.trim="promoCode" :disabled="discount > 0" dir="ltr" style="text-align:start">
        <button class="a-btn" style="white-space:nowrap" :disabled="promoBusy || !promoCode" @click="applyPromo">{{ t('checkout.apply') }}</button>
      </div>
      <p v-if="promoErr" style="color:var(--red);font-size:.82rem;margin-top:.3rem">{{ promoErr }}</p>
      <p v-if="discount > 0" style="color:var(--green);font-size:.85rem;margin-top:.3rem">✓ {{ t('checkout.promoApplied', { p: appliedPercent, amount: ar(discount) }) }}</p>

      <div style="margin-top:.7rem;font-size:.9rem;border-top:1px solid rgba(60,74,39,.12);padding-top:.6rem">
        <div class="a-row"><span class="a-muted">{{ t('checkout.subtotal') }}</span><span>{{ ar(cart.total) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
        <div v-if="discount > 0" class="a-row"><span class="a-muted">{{ t('checkout.discountLine') }}</span><span style="color:var(--green)">− {{ ar(discount) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
        <div class="a-row"><span class="a-muted">{{ t('checkout.deliveryFee') }}</span>
          <span v-if="deliveryFeeAmount > 0">{{ ar(deliveryFeeAmount) }} <span class='dh' role='img' aria-label='درهم'></span></span>
          <span v-else style="color:var(--green)">{{ t('checkout.freeDelivery') }}</span>
        </div>
        <div class="a-row" style="font-weight:700;margin-top:.2rem"><span>{{ t('checkout.total') }}</span><span>{{ ar(finalTotal) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
      </div>

      <label class="co-l" style="margin-top:.8rem">{{ t('checkout.payMethod') }}</label>
      <label class="addr-pick" :class="{ on: payMethod === 'cod' }">
        <input type="radio" value="cod" v-model="payMethod" style="display:none"> {{ t('checkout.cod') }}
      </label>
      <label class="addr-pick" :class="{ on: payMethod === 'ziina' }">
        <input type="radio" value="ziina" v-model="payMethod" style="display:none"> {{ t('checkout.ziina') }}
      </label>

      <p v-if="coErr" style="color:var(--red);font-size:.85rem;margin-top:.6rem">{{ coErr }}</p>
      <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="placing" @click="placeOrder">
        {{ placing ? t('checkout.placing') : `${payMethod === 'ziina' ? t('checkout.payAndConfirm') : t('checkout.confirm')} — ${ar(finalTotal)}` }} <span v-if="!placing" class='dh' role='img' aria-label='درهم'></span>
      </button>
    </div>
  </div>
  </transition>

  <transition name="v"><button v-if="showTop" class="to-top" @click="toTop" aria-label="إلى الأعلى"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg></button></transition>

  <transition name="v"><div class="toast" v-if="toast"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>{{ toast }}</div></transition>
</template>

<script>
// named so <keep-alive include="HomeView"> in App.vue matches this view
export default { name: 'HomeView' }
</script>

<script setup>
import { ref, reactive, computed, watch, onMounted, onActivated, nextTick } from 'vue'
import { RouterLink, useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'
import { useAuthStore } from '../stores/auth'
import { useOrdersStore } from '../stores/orders'
import { useAddressesStore } from '../stores/addresses'
import { useContentStore } from '../stores/content'
import { useSettingsStore } from '../stores/settings'
import { useCatalogStore } from '../stores/catalog'
import { deliveryFee, EMIRATES } from '../utils/delivery'
import ProductFeed from '../components/ProductFeed.vue'
import CartDrawer from '../components/CartDrawer.vue'
import PortalBar from '../components/PortalBar.vue'
import ImagePicker from '../components/ImagePicker.vue'
import { normalizeUaePhone } from '../utils/phone'

const { t, locale } = useI18n()
const cart = useCartStore()
const auth = useAuthStore()
const pantryFeed = ref(null)
const potteryFeed = ref(null)
const ordersStore = useOrdersStore()
const addresses = useAddressesStore()
const content = useContentStore()
const settings = useSettingsStore()
const catalog = useCatalogStore()
const router = useRouter()
const route = useRoute()
const ar = (n) => String(n)

// bundled defaults — used until the editable cards load (and for the nav link labels)
const fallbackValues = computed(() => [
  { icon: `<img src='/images/badge-asli.png' alt=''>`, link: '#pantry', t: t('values.v1.t'), d: t('values.v1.d'), more: t('values.v1.more'), linkLabel: t('values.v1.linkLabel') },
  { icon: `<img src='/images/badge-ard.png' alt=''>`, link: '#story', t: t('values.v2.t'), d: t('values.v2.d'), more: t('values.v2.more'), linkLabel: t('values.v2.linkLabel') },
  { icon: `<img src='/images/badge-jawda.png' alt=''>`, link: '#pantry', t: t('values.v3.t'), d: t('values.v3.d'), more: t('values.v3.more'), linkLabel: t('values.v3.linkLabel') },
  { icon: `<img src='/images/badge-tawsil.png' alt=''>`, link: '#contact', t: t('values.v4.t'), d: t('values.v4.d'), more: t('values.v4.more'), linkLabel: t('values.v4.linkLabel') },
])
// admin-editable cards from the backend, mapped to the active language (falls back to Arabic, then to the bundled defaults)
const values = computed(() => {
  if (!content.values.length) return fallbackValues.value
  return content.values.map((row, i) => {
    const fb = fallbackValues.value[i] || {}
    const pick = (ar, en) => (locale.value === 'ar' ? ar : (en || ar)) || ''
    return {
      id: row.id,
      raw: row,
      icon: row.image_url ? `<img src='${row.image_url}' alt=''>` : fb.icon,
      link: row.link || fb.link,
      linkLabel: fb.linkLabel,
      t: pick(row.title_ar, row.title_en),
      d: pick(row.desc_ar, row.desc_en),
      more: pick(row.more_ar, row.more_en),
    }
  })
})

// inline editing (managers only)
const editingValue = ref(null)
const evImages = ref([])
const evBusy = ref(false)

function onValueClick(v) {
  if (auth.isManager && v.id) {
    editingValue.value = { ...v.raw }
    evImages.value = v.raw.image_url ? [v.raw.image_url] : []
  } else {
    modal.value = v
  }
}
async function saveValue() {
  evBusy.value = true
  try {
    const r = editingValue.value
    await content.updateValue(r.id, {
      image_url: evImages.value[0] || null,
      title_ar: r.title_ar, title_en: r.title_en,
      desc_ar: r.desc_ar, desc_en: r.desc_en,
      more_ar: r.more_ar, more_en: r.more_en,
    })
    editingValue.value = null
    showToast(t('manager.vcSaved'))
  } catch (e) {
    showToast(e.message)
  } finally {
    evBusy.value = false
  }
}

const scrolled = ref(false)
const mobileMenu = ref(false)
const openCart = ref(false)
const badgePop = ref(false)
const toast = ref('')
const email = ref('')
const modal = ref(null)
const showTop = ref(false)
const activeSection = ref('home')

// storefront type filters (data-driven from the products in each category)
const pantryTypes = ref([])
const potteryTypes = ref([])
const pantryType = ref('')
const potteryType = ref('')

// product search
const searchQuery = ref('')   // what the customer is typing
const activeQuery = ref('')   // debounced term actually sent to the API
const searchHidden = ref(false) // search bar auto-hidden while scrolling down
const searching = computed(() => activeQuery.value.trim().length > 0)
let searchTimer
watch(searchQuery, (v) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { activeQuery.value = v.trim() }, 300)
})

const checkoutOpen = ref(false)
const coErr = ref('')
const placing = ref(false)
const co = reactive({ name: '', phone: '', city: '', street: '', house: '', notes: '' })
const selectedAddressId = ref(null)
const newAddress = ref(false)
const saveAddress = ref(false)
const payMethod = ref('cod')
const promoCode = ref('')
const promoBusy = ref(false)
const promoErr = ref('')
const discount = ref(0)
const appliedPercent = ref(0)
const appliedCode = ref(null)
// delivery city = the chosen saved address, or the typed one
const deliveryCity = computed(() => {
  const usingSaved = auth.isAuthenticated && addresses.addresses.length && !newAddress.value
  if (usingSaved) return addresses.addresses.find((a) => a.id === selectedAddressId.value)?.city || ''
  return co.city
})
const deliveryFeeAmount = computed(() => deliveryFee(deliveryCity.value, cart.total, settings.delivery))
const finalTotal = computed(() => Math.max(0, Math.round((cart.total - discount.value + deliveryFeeAmount.value) * 100) / 100))

async function applyPromo() {
  promoErr.value = ''
  promoBusy.value = true
  try {
    const r = await ordersStore.validateCode(promoCode.value, cart.total)
    discount.value = r.discount
    appliedPercent.value = r.percent
    appliedCode.value = r.code
  } catch (e) {
    promoErr.value = e.message
    discount.value = 0
    appliedCode.value = null
  } finally {
    promoBusy.value = false
  }
}

let toastTimer
function showToast(m) {
  toast.value = m
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2600)
}
function flashBadge() {
  badgePop.value = false
  nextTick(() => {
    badgePop.value = true
    setTimeout(() => (badgePop.value = false), 400)
  })
}
function onAdded(p) {
  flashBadge()
  showToast(t('cart.added', { name: p.name }))
}
function subscribe() {
  showToast(t('home.subscribed'))
  email.value = ''
}
function toTop() {
  scrollTo({ top: 0, behavior: 'smooth' })
}

async function openCheckout() {
  if (!cart.list.length) return
  openCart.value = false
  // reset any previously-applied promo
  promoCode.value = ''
  promoErr.value = ''
  discount.value = 0
  appliedCode.value = null
  // checkout requires an account so the order is trackable under the customer
  if (!auth.isAuthenticated) {
    showToast(t('checkout.loginRequired'))
    router.push({ name: 'login', query: { redirect: '/' } })
    return
  }
  coErr.value = ''
  newAddress.value = false
  co.name = co.name || auth.user.full_name || ''
  co.phone = co.phone || auth.user.phone || ''
  await addresses.fetch().catch(() => {})
  selectedAddressId.value = addresses.default?.id || null
  if (!addresses.addresses.length) newAddress.value = true
  checkoutOpen.value = true
}

async function placeOrder() {
  coErr.value = ''
  let delivery
  const usingSaved = auth.isAuthenticated && addresses.addresses.length && !newAddress.value
  if (usingSaved) {
    const a = addresses.addresses.find((x) => x.id === selectedAddressId.value)
    if (!a) { coErr.value = t('checkout.errChoose'); return }
    delivery = { customer_name: co.name || auth.user?.full_name || '—', phone: co.phone || auth.user?.phone || '', city: a.city, street: a.street, house: a.house, notes: a.notes }
    if (!delivery.phone) { coErr.value = t('checkout.errPhone'); return }
  } else {
    if (!co.name || !co.phone || !co.city || !co.street || !co.house) {
      coErr.value = t('checkout.errRequired')
      return
    }
    delivery = { customer_name: co.name, phone: co.phone, city: co.city, street: co.street, house: co.house, notes: co.notes }
  }

  // delivery phone must be a valid UAE mobile
  const normPhone = normalizeUaePhone(delivery.phone)
  if (!normPhone) { coErr.value = t('auth.errPhoneUAE'); return }
  delivery.phone = normPhone

  placing.value = true
  try {
    const items = cart.list.map((i) => ({ product_id: i.id, qty: i.q }))
    // save a new address before any redirect happens
    if (saveAddress.value && auth.isAuthenticated && !usingSaved) {
      await addresses.add({ city: co.city, street: co.street, house: co.house, notes: co.notes, label: t('checkout.defaultAddrLabel') }).catch(() => {})
    }
    const result = await ordersStore.place(delivery, items, payMethod.value, appliedCode.value)
    // Ziina → hand off to the hosted payment page
    if (result.redirect_url) {
      cart.clear()
      window.location.href = result.redirect_url
      return
    }
    // Cash on delivery
    cart.clear()
    checkoutOpen.value = false
    saveAddress.value = false
    Object.assign(co, { name: '', phone: '', city: '', street: '', house: '', notes: '' })
    pantryFeed.value?.reload(); potteryFeed.value?.reload() // refresh stock
    showToast(t('checkout.received', { id: result.order.id.slice(0, 8) }))
  } catch (e) {
    coErr.value = e.message
  } finally {
    placing.value = false
  }
}

watch(() => auth.isAuthenticated, () => {}) // keep header reactive

// delivery config is only needed for the cart note + checkout — fetch it lazily, once
let deliveryLoaded = false
watch(openCart, (open) => {
  if (open && !deliveryLoaded) { deliveryLoaded = true; settings.fetchDelivery() }
})

// arriving from the product page's "checkout" button — runs on first mount and
// on every re-activation, since keep-alive means onMounted fires only once
function maybeOpenCheckout() {
  if (route.query.checkout && cart.list.length) {
    openCheckout()
    router.replace({ query: {} })
  }
}
// fires on first render and on every return to the storefront
onActivated(maybeOpenCheckout)

// scroll-reveal for sec-heads, value cards and the story block. Kept at setup
// scope (not inside onMounted) so it can re-run whenever content loads: the
// value cards re-render with new keys once content.fetch() resolves, replacing
// their DOM nodes — without re-observing, those fresh nodes stay at opacity:0.
let revealIO = null
function observeReveals() {
  if (!revealIO) {
    revealIO = new IntersectionObserver((es) => {
      es.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('in'); revealIO.unobserve(e.target) }
      })
    }, { threshold: 0.14 })
  }
  // product cards reveal themselves inside ProductFeed
  nextTick(() => document.querySelectorAll('.reveal:not(.in)').forEach((el) => revealIO.observe(el)))
}
// re-observe when the editable "why us" cards arrive from the backend
watch(() => content.values, observeReveals)

onMounted(() => {
  content.fetch()
  // load the filter chips for each section
  catalog.fetchTypes('pantry').then((t) => (pantryTypes.value = t)).catch(() => {})
  catalog.fetchTypes('pottery').then((t) => (potteryTypes.value = t)).catch(() => {})
  // keep the sticky search bar sitting right under the nav (height varies by breakpoint)
  const updateNavH = () => {
    const nav = document.querySelector('.portal-bar')
    if (nav) document.documentElement.style.setProperty('--nav-h', nav.offsetHeight + 'px')
  }
  nextTick(updateNavH)
  addEventListener('resize', updateNavH, { passive: true })
  const navSections = ['home', 'pantry', 'pottery', 'story', 'contact']
  function updateActiveSection() {
    const line = scrollY + innerHeight * 0.3 // a bit below the sticky header
    let current = navSections[0]
    for (const id of navSections) {
      const el = document.getElementById(id)
      if (el && el.offsetTop <= line) current = id
    }
    // near the very bottom, force the last section active
    if (innerHeight + scrollY >= document.body.scrollHeight - 4) current = navSections[navSections.length - 1]
    activeSection.value = current
  }
  let lastY = scrollY
  addEventListener('scroll', () => {
    scrolled.value = scrollY > 10
    showTop.value = scrollY > 620
    // search bar: visible near the top, hides when scrolling down, returns on scroll up
    const y = scrollY
    if (y < 140) searchHidden.value = false
    else if (y > lastY + 6) searchHidden.value = true
    else if (y < lastY - 6) searchHidden.value = false
    lastY = y
    updateActiveSection()
  }, { passive: true })
  updateActiveSection()
  observeReveals()
})
</script>

<style scoped>
.acct-link {
  font-weight: 700;
  color: var(--green);
  padding: .35rem .7rem;
  border-radius: 10px;
  background: var(--cream-2, rgba(60,74,39,.08));
  font-size: .9rem;
  white-space: nowrap;
}
.addr-pick {
  display: block;
  border: 1.5px solid rgba(60,74,39,.2);
  border-radius: 12px;
  padding: .6rem .8rem;
  margin-bottom: .5rem;
  cursor: pointer;
  font-size: .9rem;
  transition: border-color .15s, background .15s;
}
.addr-pick.on { border-color: var(--green); background: rgba(60,74,39,.06); }
.search-bar {
  position: sticky;
  top: var(--nav-h, 56px);
  z-index: 55;
  background: var(--cream, #f5efe3);
  padding: .55rem 1.4rem;
  transition: transform .3s ease;
}
.search-bar.hidden { transform: translateY(calc(-100% - var(--nav-h, 56px))); }
.search-inner {
  max-width: 640px; margin: 0 auto;
  display: flex; align-items: center; gap: .5rem;
  background: #fff; border: 1.5px solid rgba(60,74,39,.2);
  border-radius: 999px; padding: .5rem .95rem;
  transition: border-color .15s, box-shadow .15s;
}
.search-inner:focus-within { border-color: var(--green); box-shadow: 0 6px 20px -12px rgba(60,74,39,.6); }
.search-ic { width: 20px; height: 20px; color: var(--green); flex: 0 0 auto; }
.search-input {
  flex: 1; border: none; outline: none; background: transparent;
  font-family: inherit; font-size: .95rem; color: var(--ink);
}
.search-input::-webkit-search-cancel-button { display: none; }
.search-clear {
  width: 26px; height: 26px; flex: 0 0 auto; display: grid; place-items: center;
  border-radius: 50%; background: var(--cream-2, rgba(60,74,39,.08)); color: var(--green); cursor: pointer;
}
.search-clear svg { width: 15px; height: 15px; }
.search-results { padding-top: 2rem; min-height: 60vh; }
@media (max-width: 560px) { .search-bar { padding: .5rem 1rem; } }
.type-filter {
  display: flex; flex-wrap: wrap; gap: .5rem;
  margin: 0 0 1.6rem; justify-content: center;
}
.type-chip {
  padding: .45rem 1.1rem; border-radius: 999px;
  border: 1.5px solid rgba(60,74,39,.22); background: transparent;
  color: var(--green); font-family: inherit; font-size: .9rem; font-weight: 600;
  cursor: pointer; transition: background .15s, color .15s, border-color .15s;
}
.type-chip:hover { border-color: var(--green); }
.type-chip.on { background: var(--green); color: #fff; border-color: var(--green); }
.value { position: relative; }
.v-edit {
  position: absolute; top: 6px; inset-inline-end: 6px;
  width: 22px; height: 22px; display: grid; place-items: center;
  border-radius: 6px; color: var(--gold, #b8902f); background: rgba(184,144,47,.14);
}
.v-edit svg { width: 13px; height: 13px; }
</style>
