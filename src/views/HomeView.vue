<template>
  <div class="topbar"><transition name="fade" mode="out-in"><span class="tb-msg" :key="tbi" v-html="topbarMsgs[tbi]"></span></transition></div>

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
  <div class="wrap mobile-menu" :class="{ show: mobileMenu }">
    <a href="#pantry" @click="mobileMenu = false">{{ t('nav.pantry') }}</a><a href="#pottery" @click="mobileMenu = false">{{ t('nav.pottery') }}</a><a href="#story" @click="mobileMenu = false">{{ t('nav.story') }}</a><a href="#contact" @click="mobileMenu = false">{{ t('nav.contact') }}</a>
    <RouterLink v-if="auth.isAuthenticated" to="/account">{{ t('nav.account') }}</RouterLink>
    <RouterLink v-else to="/login">{{ t('auth.loginTitle') }}</RouterLink>
  </div>

  <!-- hero -->
  <section class="hero" id="home">
    <img class="hero-img" src="/images/hero.jpg" alt="دكّان كنعان — مونة وفخّار فلسطيني" /><a class="scroll-cue" href="#pantry" aria-label="استكشف المتجر"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></a>
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
    <button class="value reveal" v-for="v in values" :key="v.t" @click="modal = v"><span class="ic" v-html="v.icon"></span><div><b>{{ v.t }}</b><span>{{ v.d }}</span></div></button>
  </div></div>

  <!-- pantry -->
  <section id="pantry">
    <div class="wrap">
      <div class="sec-head reveal"><span class="eyebrow">{{ t('home.pantryEyebrow') }}</span><h2 class="display">{{ t('home.pantryTitle') }}</h2><p>{{ t('home.pantryDesc') }}</p></div>
      <p v-if="catalog.loading" class="a-muted" style="text-align:center">{{ t('common.loading') }}</p>
      <p v-else-if="catalog.error" class="a-muted" style="text-align:center;color:var(--red)">{{ t('home.loadError') }}: {{ catalog.error }}</p>
      <div class="grid">
        <ProductCard v-for="(p, i) in catalog.pantry" :key="p.id" :product="p" :index="i" @added="onAdded" />
      </div>
    </div>
  </section>

  <div class="divider" aria-hidden="true"><img src="/images/dome.jpg" alt=""></div>

  <!-- pottery -->
  <section class="pottery" id="pottery">
    <div class="wrap">
      <div class="sec-head reveal"><span class="eyebrow">{{ t('home.potteryEyebrow') }}</span><h2 class="display">{{ t('home.potteryTitle') }}</h2><p>{{ t('home.potteryDesc') }}</p></div>
      <div class="grid">
        <ProductCard v-for="(p, i) in catalog.pottery" :key="p.id" :product="p" :index="i" @added="onAdded" />
      </div>
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

  <!-- newsletter -->
  <section class="news" id="contact"><div class="wrap inner">
    <div class="reveal"><h2 class="display">{{ t('home.newsTitle') }}</h2><p>{{ t('home.newsDesc') }}</p></div>
    <form class="reveal" @submit.prevent="subscribe"><input type="email" v-model="email" :placeholder="t('home.newsPlaceholder')" :aria-label="t('home.newsPlaceholder')" required><button type="submit" class="btn btn-gold">{{ t('home.subscribe') }}</button></form>
  </div></section>

  <footer class="site">
    <div class="band" aria-hidden="true"></div>
    <div class="wrap fcols">
      <div class="about"><div class="name display"><span class="g">دكّان</span> كنعان</div><p>{{ t('footer.about') }}</p></div>
      <div><h5>{{ t('footer.shop') }}</h5><a href="#pantry">{{ t('nav.pantry') }}</a><a href="#pottery">{{ t('nav.pottery') }}</a><a href="#pantry">{{ t('footer.harvest') }}</a><a href="#pantry">{{ t('footer.gifts') }}</a></div>
      <div><h5>{{ t('footer.links') }}</h5><a href="#story">{{ t('nav.story') }}</a><a href="#contact">{{ t('footer.contactUs') }}</a><RouterLink to="/account">{{ t('nav.account') }}</RouterLink><a href="#">{{ t('footer.faq') }}</a></div>
      <div><h5>{{ t('footer.contact') }}</h5><a href="#">واتساب: 059 000 000</a><a href="#">ahla@kanaan.ps</a><a href="#">إنستغرام @dukkan.kanaan</a></div>
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
          <b>{{ a.label || '—' }}</b> — {{ a.city }}، {{ a.street }}، {{ a.house }}
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
          <div><label class="co-l">{{ t('checkout.city') }} *</label><input class="a-input" v-model.trim="co.city"></div>
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

      <p v-if="coErr" style="color:var(--red);font-size:.85rem;margin-top:.6rem">{{ coErr }}</p>
      <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="placing" @click="placeOrder">
        {{ placing ? t('checkout.placing') : `${t('checkout.confirm')} — ${ar(cart.total)}` }} <span v-if="!placing" class='dh' role='img' aria-label='درهم'></span>
      </button>
      <p class="a-muted" style="text-align:center;margin-top:.6rem;font-size:.78rem">{{ t('checkout.cod') }}</p>
    </div>
  </div>
  </transition>

  <transition name="v"><button v-if="showTop" class="to-top" @click="toTop" aria-label="إلى الأعلى"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg></button></transition>

  <transition name="v"><div class="toast" v-if="toast"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>{{ toast }}</div></transition>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useCartStore } from '../stores/cart'
import { useAuthStore } from '../stores/auth'
import { useCatalogStore } from '../stores/catalog'
import { useOrdersStore } from '../stores/orders'
import { useAddressesStore } from '../stores/addresses'
import ProductCard from '../components/ProductCard.vue'
import CartDrawer from '../components/CartDrawer.vue'
import PortalBar from '../components/PortalBar.vue'
import { normalizeUaePhone } from '../utils/phone'

const { t } = useI18n()
const cart = useCartStore()
const auth = useAuthStore()
const catalog = useCatalogStore()
const ordersStore = useOrdersStore()
const addresses = useAddressesStore()
const ar = (n) => String(n)

// rotating topbar messages + "why us" cards, from the active locale
const topbarMsgs = computed(() => [t('topbar.m1'), t('topbar.m2'), t('topbar.m3')])
const values = computed(() => [
  { icon: `<img src='/images/badge-asli.png' alt=''>`, link: '#pantry', t: t('values.v1.t'), d: t('values.v1.d'), more: t('values.v1.more'), linkLabel: t('values.v1.linkLabel') },
  { icon: `<img src='/images/badge-ard.png' alt=''>`, link: '#story', t: t('values.v2.t'), d: t('values.v2.d'), more: t('values.v2.more'), linkLabel: t('values.v2.linkLabel') },
  { icon: `<img src='/images/badge-jawda.png' alt=''>`, link: '#pantry', t: t('values.v3.t'), d: t('values.v3.d'), more: t('values.v3.more'), linkLabel: t('values.v3.linkLabel') },
  { icon: `<img src='/images/badge-tawsil.png' alt=''>`, link: '#contact', t: t('values.v4.t'), d: t('values.v4.d'), more: t('values.v4.more'), linkLabel: t('values.v4.linkLabel') },
])

const scrolled = ref(false)
const mobileMenu = ref(false)
const openCart = ref(false)
const badgePop = ref(false)
const toast = ref('')
const email = ref('')
const modal = ref(null)
const showTop = ref(false)
const tbi = ref(0)
const activeSection = ref('home')

const checkoutOpen = ref(false)
const coErr = ref('')
const placing = ref(false)
const co = reactive({ name: '', phone: '', city: '', street: '', house: '', notes: '' })
const selectedAddressId = ref(null)
const newAddress = ref(false)
const saveAddress = ref(false)

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
  coErr.value = ''
  newAddress.value = false
  if (auth.user) {
    co.name = co.name || auth.user.full_name || ''
    co.phone = co.phone || auth.user.phone || ''
    await addresses.fetch().catch(() => {})
    selectedAddressId.value = addresses.default?.id || null
    if (!addresses.addresses.length) newAddress.value = true
  }
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
    const order = await ordersStore.place(delivery, items)
    if (saveAddress.value && auth.isAuthenticated && !usingSaved) {
      await addresses.add({ city: co.city, street: co.street, house: co.house, notes: co.notes, label: 'المنزل' }).catch(() => {})
    }
    cart.clear()
    checkoutOpen.value = false
    saveAddress.value = false
    Object.assign(co, { name: '', phone: '', city: '', street: '', house: '', notes: '' })
    await catalog.fetch() // refresh stock
    showToast(t('checkout.received', { id: order.id.slice(0, 8) }))
  } catch (e) {
    coErr.value = e.message
  } finally {
    placing.value = false
  }
}

watch(() => auth.isAuthenticated, () => {}) // keep header reactive

onMounted(() => {
  catalog.fetch()
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
  addEventListener('scroll', () => {
    scrolled.value = scrollY > 10
    showTop.value = scrollY > 620
    updateActiveSection()
  }, { passive: true })
  updateActiveSection()
  const io = new IntersectionObserver((es) => {
    es.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add('in')
        io.unobserve(e.target)
      }
    })
  }, { threshold: 0.14 })
  // observe reveal elements as products render
  watch(() => catalog.products.length, () => nextTick(() => document.querySelectorAll('.reveal:not(.in)').forEach((el) => io.observe(el))), { immediate: true })
  setInterval(() => {
    tbi.value = (tbi.value + 1) % topbarMsgs.value.length
  }, 3800)
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
</style>
