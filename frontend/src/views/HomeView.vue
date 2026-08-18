<template>
  <PortalBar :scrolled="scrolled" search>
    <nav class="tabs store-nav" aria-label="nav">
      <a href="#home" :class="{ active: activeSection === 'home' }">{{ t('nav.home') }}</a><a href="#pantry" :class="{ active: activeSection === 'pantry' }">{{ t('nav.pantry') }}</a><a href="#pottery" :class="{ active: activeSection === 'pottery' }">{{ t('nav.pottery') }}</a><a href="#story" :class="{ active: activeSection === 'story' }">{{ t('nav.story') }}</a><a v-if="reviews.visible" href="#reviews" :class="{ active: activeSection === 'reviews' }">{{ t('nav.reviews') }}</a><a href="#contact" :class="{ active: activeSection === 'contact' }">{{ t('nav.contact') }}</a>
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
      <a v-if="reviews.visible" href="#reviews" :class="{ active: activeSection === 'reviews' }" @click="mobileMenu = false">{{ t('nav.reviews') }}</a>
      <a href="#contact" :class="{ active: activeSection === 'contact' }" @click="mobileMenu = false">{{ t('nav.contact') }}</a>
      <RouterLink v-if="auth.isAuthenticated" to="/account" @click="mobileMenu = false">{{ t('nav.account') }}</RouterLink>
      <RouterLink v-else to="/login" @click="mobileMenu = false">{{ t('auth.loginTitle') }}</RouterLink>
    </nav>
  </aside>

  <!-- Product search — sticky under the nav; auto-hides on scroll down, returns on
       scroll up / at top. Submitting hands off to /search, the same results page
       the header's search box uses, so there's one search experience site-wide. -->
  <form class="search-bar" :class="{ hidden: searchHidden }" role="search" @submit.prevent="runSearch">
    <div class="search-inner">
      <svg class="search-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>
      <input class="search-input" v-model="searchQuery" :placeholder="t('search.placeholder')" type="search" enterkeyhint="search" :aria-label="t('search.placeholder')">
      <button v-if="searchQuery" type="button" class="search-clear" @click="searchQuery = ''" :aria-label="t('search.clear')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
      <button v-if="searchQuery.trim()" type="submit" class="search-go">{{ t('search.go') }}</button>
    </div>
  </form>

  <!-- hero -->
  <section class="hero" id="home">
    <img class="hero-img" src="/images/hero.jpg" alt="دكّان كنعان — مونة وخزف فلسطيني" fetchpriority="high" decoding="async" /><a class="scroll-cue" href="#pantry" aria-label="استكشف المتجر"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></a>
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
    <template v-if="content.loaded">
      <button class="value reveal" v-for="v in values" :key="v.id || v.t" @click="onValueClick(v)"><span class="ic" v-html="v.icon"></span><div><b>{{ v.t }}</b><span>{{ v.d }}</span></div><span v-if="auth.isManager && v.id" class="v-edit" :title="t('manager.vcEditHint')" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></span></button>
    </template>
    <!-- one loader for the whole section while /api/content/values loads; the real
         cards render once it responds -->
    <Loader v-if="!content.loaded" class="values-loading" />
  </div></div>

  <!-- pantry -->
  <section id="pantry">
    <div class="wrap">
      <div class="sec-head reveal"><span class="eyebrow">{{ t('home.pantryEyebrow') }}</span><h2 class="display">{{ t('home.pantryTitle') }}</h2><p>{{ t('home.pantryDesc') }}</p></div>
      <ProductFeed ref="pantryFeed" category="pantry" :page-size="8" preview @added="onAdded" />
      <div class="sec-more"><RouterLink class="btn btn-green" :to="{ name: 'category', params: { cat: 'pantry' } }">{{ t('home.showAll') }}</RouterLink></div>
    </div>
  </section>

  <!-- pottery -->
  <section class="pottery" id="pottery">
    <div class="wrap">
      <div class="sec-head reveal"><span class="eyebrow">{{ t('home.potteryEyebrow') }}</span><h2 class="display">{{ t('home.potteryTitle') }}</h2><p>{{ t('home.potteryDesc') }}</p></div>
      <ProductFeed ref="potteryFeed" category="pottery" :page-size="8" preview @added="onAdded" />
      <div class="sec-more"><RouterLink class="btn btn-green" :to="{ name: 'category', params: { cat: 'pottery' } }">{{ t('home.showAll') }}</RouterLink></div>
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

  <!-- what customers say about the shop (general reviews, not per product) — last
       thing on the page, after the story -->
  <ReviewsSection ref="reviewsSection" />

  <footer class="site" id="contact">
    <div class="band" aria-hidden="true"></div>
    <div class="wrap fcols">
      <div class="about"><div class="name display"><span class="g">دكّان</span> كنعان</div><p>{{ t('footer.about') }}</p></div>
      <div><h5>{{ t('footer.shop') }}</h5><a href="#pantry">{{ t('nav.pantry') }}</a><a href="#pottery">{{ t('nav.pottery') }}</a></div>
      <div><h5>{{ t('footer.links') }}</h5><a href="#story">{{ t('nav.story') }}</a><a href="#" @click.prevent="contactUs">{{ t('footer.contactUs') }}</a><RouterLink to="/track">{{ t('track.findOrder') }}</RouterLink><RouterLink to="/account">{{ t('nav.account') }}</RouterLink></div>
      <div><h5>{{ t('footer.contact') }}</h5>
        <a href="https://wa.me/971522981187" target="_blank" rel="noopener">{{ t('footer.whatsapp') }}: <span dir="ltr">+971 52 298 1187</span></a>
        <a href="mailto:dukkan.kanaan@gmail.com">dukkan.kanaan@gmail.com</a>
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

  <!-- guest order placed: their only route back to the order, so it's on screen
       as well as in the confirmation e-mail -->
  <transition name="v">
    <div class="modal-overlay" v-if="placed" @click.self="placed = null">
      <div class="modal">
        <button class="m-close" @click="placed = null" :aria-label="t('common.close')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
        <span class="m-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg></span>
        <h3 class="display">{{ t('checkout.placedTitle') }}</h3>
        <p>{{ t('checkout.received', { id: placed.id.slice(0, 8) }) }}</p>
        <p class="a-muted" style="margin:.5rem 0 .9rem">{{ t('checkout.placedEmailed') }}</p>
        <RouterLink class="btn btn-green" :to="{ name: 'track', params: { id: placed.id }, query: { t: placed.token } }" @click="placed = null">
          {{ t('checkout.trackOrder') }}
        </RouterLink>
        <p class="a-muted" style="margin-top:.9rem;font-size:.82rem">
          {{ t('checkout.placedSignupNudge') }}
          <RouterLink to="/register" class="lnk" @click="placed = null">{{ t('auth.registerTitle') }}</RouterLink>
        </p>
      </div>
    </div>
  </transition>

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
      <p class="a-muted" style="text-align:center;margin-bottom:.6rem">{{ t('checkout.subtitle', { count: ar(cart.count), total: ar(finalTotal) }) }}</p>

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
        <!-- Ordering as a guest works, but the order lives on a link rather than in
             an account — say so plainly before they type anything. -->
        <div v-if="!auth.isAuthenticated" class="guest-warn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 9v4"/><path d="M12 17h.01"/><circle cx="12" cy="12" r="9"/></svg>
          <span>
            {{ t('checkout.guestWarn') }}
            <RouterLink to="/login" class="lnk">{{ t('checkout.loginWord') }}</RouterLink>
          </span>
        </div>
        <label class="co-l">{{ t('checkout.fullName') }} *</label>
        <input class="a-input" v-model.trim="co.name">
        <label class="co-l">{{ t('checkout.phone') }} *</label>
        <input class="a-input" v-model.trim="co.phone" type="tel" inputmode="tel" dir="ltr" placeholder="050 123 4567">
        <!-- guests only: the second way to reach them if the phone is wrong, and
             where the tracking link is sent -->
        <template v-if="!auth.isAuthenticated">
          <label class="co-l">{{ t('checkout.email') }} *</label>
          <input class="a-input" v-model.trim="co.email" type="email" inputmode="email" dir="ltr" autocomplete="email" placeholder="you@example.com">
          <p class="a-muted" style="font-size:.78rem;margin-top:.25rem">{{ t('checkout.emailWhy') }}</p>
        </template>
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
        <div v-if="discount > 0" class="a-row"><span class="a-muted">{{ t('checkout.discountLine') }}</span><span style="color:var(--red)">− {{ ar(discount) }} <span class='dh' role='img' aria-label='درهم'></span></span></div>
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
import { useReviewsStore } from '../stores/reviews'
import { useSettingsStore } from '../stores/settings'
import { useInboxStore } from '../stores/inbox'
import { deliveryFee, EMIRATES } from '../utils/delivery'
import ProductFeed from '../components/ProductFeed.vue'
import ReviewsSection from '../components/ReviewsSection.vue'
import CartDrawer from '../components/CartDrawer.vue'
import PortalBar from '../components/PortalBar.vue'
import ImagePicker from '../components/ImagePicker.vue'
import Loader from '../components/Loader.vue'
import { normalizeUaePhone } from '../utils/phone'
import { pName } from '../utils/product'

const { t, locale } = useI18n()
const cart = useCartStore()
const auth = useAuthStore()
const pantryFeed = ref(null)
const potteryFeed = ref(null)
const reviewsSection = ref(null)
const ordersStore = useOrdersStore()
const addresses = useAddressesStore()
const content = useContentStore()
const reviews = useReviewsStore() // only for the nav link's visibility (see its store)
const settings = useSettingsStore()
const inbox = useInboxStore()

// "Contact us" opens the in-app chat with the shop (login first if a guest)
function contactUs() {
  if (auth.isAuthenticated) inbox.requestChat()
  else router.push({ name: 'login', query: { redirect: '/' } })
}
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
  // wait for the API before showing anything — avoids flashing the bundled defaults
  // and then swapping to the admin-edited cards (a skeleton shows meanwhile)
  if (!content.loaded) return []
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

// product search
const searchQuery = ref('')     // what the customer is typing
const searchHidden = ref(false) // search bar auto-hidden while scrolling down

// Hand off to the shared /search page rather than swapping the storefront's
// content for results — one results view for both this field and the header box.
function runSearch() {
  const q = searchQuery.value.trim()
  if (q) router.push({ name: 'search', query: { q } })
}
const checkoutOpen = ref(false)
const coErr = ref('')
const placing = ref(false)
const co = reactive({ name: '', phone: '', city: '', street: '', house: '', notes: '', email: '' })
// set after a guest's order goes through: { id, token } for the tracking link
const placed = ref(null)
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
  showToast(t('cart.added', { name: pName(p) }))
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
  coErr.value = ''
  newAddress.value = false
  // Guests: allowed only if the manager turned guest checkout on. Otherwise it's
  // the old flow — sign in first, and '/?checkout=1' reopens the checkout after.
  if (!auth.isAuthenticated) {
    if (!settings.checkoutLoaded) await settings.fetchCheckout()
    if (!settings.checkout.guest_allowed) {
      showToast(t('checkout.loginRequired'))
      router.push({ name: 'login', query: { redirect: '/?checkout=1' } })
      return
    }
    // they type the same delivery details plus an e-mail, and get a tracking link
    // instead of an order history. No saved addresses, so go straight to the form.
    newAddress.value = true
    checkoutOpen.value = true
    return
  }
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
    // a guest is reachable only by what they type here, so the e-mail is required
    if (!auth.isAuthenticated) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(co.email)) { coErr.value = t('checkout.errEmail'); return }
      delivery.email = co.email
    }
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
    const wasGuest = !auth.isAuthenticated
    cart.clear()
    checkoutOpen.value = false
    saveAddress.value = false
    Object.assign(co, { name: '', phone: '', city: '', street: '', house: '', notes: '', email: '' })
    pantryFeed.value?.reload(); potteryFeed.value?.reload() // refresh stock
    // A guest has no حسابي to find the order in, so hand them the tracking link on
    // screen as well as by e-mail — the e-mail address could have a typo in it.
    if (wasGuest) placed.value = { id: result.order.id, token: result.order.track_token }
    else showToast(t('checkout.received', { id: result.order.id.slice(0, 8) }))
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
  if (open && !deliveryLoaded) {
    deliveryLoaded = true
    settings.fetchDelivery()
    if (!auth.isAuthenticated) settings.fetchCheckout() // decides guest vs. sign-in first
  }
})

// arriving from the product page's "checkout" button — runs on first mount and
// on every re-activation, since keep-alive means onMounted fires only once
function maybeOpenCheckout() {
  if (route.query.checkout && cart.list.length) {
    // clear the flag FIRST — otherwise this replace() cancels the redirect that
    // openCheckout() fires when the shopper isn't signed in (that was the bug:
    // checkout from a product page showed the toast but never reached /login).
    router.replace({ query: {} })
    openCheckout()
  }
}
// arriving from the reviews section's "write a review" button after signing in —
// scroll back to the section and reopen the form they were sent away from
function maybeOpenReview() {
  if (!route.query.review) return
  router.replace({ query: {} })
  nextTick(() => {
    document.getElementById('reviews')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    reviewsSection.value?.openForm()
  })
}
// fires on first render and on every return to the storefront
onActivated(maybeOpenCheckout)
onActivated(maybeOpenReview)

// scroll-reveal for sec-heads, value cards and the story block. Kept at setup
// scope (not inside onMounted) so it can re-run whenever content loads: the
// value cards re-render with new keys once content.fetch() resolves, replacing
// their DOM nodes — without re-observing, those fresh nodes stay at opacity:0.
let revealIO = null
function observeReveals() {
  if (!revealIO) {
    revealIO = new IntersectionObserver((es) => {
      es.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.remove('pre'); e.target.classList.add('in'); revealIO.unobserve(e.target) }
      })
    }, { threshold: 0.14 })
  }
  // Elements already in view stay visible (no flash on prerendered content); only
  // below-the-fold ones get hidden (.pre) and animate in as they scroll into view.
  // product cards reveal themselves inside ProductFeed
  nextTick(() => document.querySelectorAll('.reveal:not(.in):not(.pre)').forEach((el) => {
    if (el.getBoundingClientRect().top > innerHeight * 0.9) { el.classList.add('pre'); revealIO.observe(el) }
    else el.classList.add('in')
  }))
}
// re-observe when the editable "why us" cards arrive from the backend
watch(() => content.values, observeReveals)

onMounted(() => {
  content.fetch()
  // keep the sticky search bar sitting right under the nav (height varies by breakpoint)
  const updateNavH = () => {
    const nav = document.querySelector('.portal-bar')
    if (nav) document.documentElement.style.setProperty('--nav-h', nav.offsetHeight + 'px')
  }
  nextTick(updateNavH)
  addEventListener('resize', updateNavH, { passive: true })
  const navSections = ['home', 'pantry', 'pottery', 'story', 'reviews', 'contact']
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
.guest-warn {
  display: flex; gap: .5rem; align-items: flex-start;
  background: rgba(184,144,47,.12); border: 1px solid rgba(184,144,47,.4);
  border-radius: 12px; padding: .6rem .75rem; margin-bottom: .8rem;
  font-size: .82rem; color: var(--ink);
}
.guest-warn svg { width: 17px; height: 17px; flex: 0 0 auto; color: var(--gold); margin-top: .15rem; }
.lnk { color: var(--green); text-decoration: underline; font-weight: 700; }
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
.search-go {
  flex: 0 0 auto; padding: .3rem .8rem; border-radius: 999px;
  background: var(--green); color: var(--cream);
  font-family: inherit; font-size: .82rem; font-weight: 700; cursor: pointer;
  transition: background .15s;
}
.search-go:hover { background: var(--gold); }
@media (max-width: 560px) { .search-bar { padding: .5rem 1rem; } }
.sec-more { text-align: center; margin-top: 1.6rem; }
/* same width as the reviews section's buttons, so the storefront's section CTAs
   all read as one control rather than three sizes */
.sec-more .btn { min-width: var(--cta-w); justify-content: center; }
@media (max-width: 560px) { .sec-more .btn { width: 100%; } }
.value { position: relative; }
/* the values loader spans the whole row (grid is repeat(3,1fr)) and centers */
.values-loading { grid-column: 1 / -1; }
.v-edit {
  position: absolute; top: 6px; inset-inline-end: 6px;
  width: 22px; height: 22px; display: grid; place-items: center;
  border-radius: 6px; color: var(--gold, #b8902f); background: rgba(184,144,47,.14);
}
.v-edit svg { width: 13px; height: 13px; }
</style>
