<template>
  <!-- Hidden until a review is approved (see the store's `visible` getter). The
       component itself always mounts, so the fetch that decides this still runs. -->
  <section v-if="reviews.visible" class="reviews" id="reviews">
    <div class="wrap">
      <div class="sec-head reveal">
        <!-- each line is optional: emptying it in the dashboard removes it -->
        <span v-if="copy.eyebrow" class="eyebrow">{{ copy.eyebrow }}</span>
        <h2 v-if="copy.title" class="display">{{ copy.title }}</h2>
        <p v-if="copy.desc">{{ copy.desc }}</p>
        <div v-if="reviews.total" class="rv-summary">
          <!-- the exact average, filled fractionally: 4.6 must not draw as five -->
          <Stars :value="reviews.average || 0" />
          <span>{{ countLabel }}</span>
        </div>
      </div>

      <Loader v-if="reviews.loading && !reviews.list.length" />

      <div v-else-if="reviews.list.length" class="rv-grid">
        <article class="rv-card reveal" v-for="r in reviews.list" :key="r.id">
          <Stars :value="r.rating" />
          <blockquote>{{ r.body }}</blockquote>
          <!-- the customer's photo, if they attached one; opens full size in a tab -->
          <a v-if="r.thumb_url || r.image_url" class="rv-shot" :href="r.image_url || r.thumb_url" target="_blank" rel="noopener">
            <img :src="r.thumb_url || r.image_url" :alt="t('reviews.photoOf', { name: r.author || t('reviews.anonymous') })" loading="lazy">
          </a>
          <footer>
            <!-- the reference design puts a round portrait here; we hold no photo
                 or country for a reviewer, so it's their initial on a gold disc -->
            <span class="rv-av" aria-hidden="true">{{ initial(r.author) }}</span>
            <div class="rv-who">
              <b>{{ r.author || t('reviews.anonymous') }}</b>
              <span v-if="r.city">{{ r.city }}</span>
            </div>
          </footer>
        </article>
      </div>

      <p v-else-if="reviews.loaded" class="a-muted rv-empty">{{ t('reviews.empty') }}</p>

      <div class="rv-actions">
        <button v-if="reviews.hasMore" class="btn btn-gold" :disabled="reviews.loading" @click="reviews.loadMore()">
          <!-- same label as the pantry/pottery sections' button, and short enough
               to never outgrow the fixed button width -->
          {{ reviews.loading ? t('common.loading') : t('home.showAll') }}
        </button>
        <button class="btn btn-green" @click="openForm">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          {{ reviews.mine ? t('reviews.editMine') : t('reviews.write') }}
        </button>
      </div>

      <!-- where the customer's own review stands (only they see this). Deleting it
           lives inside the edit form, next to the other things they can change. -->
      <p v-if="mineNote" class="rv-mine" :class="reviews.mine.status">{{ mineNote }}</p>
    </div>
  </section>

  <!-- Write / edit form. A root-level sibling of the section, so it keeps working
       even in the window where the section itself is still hidden. -->
  <transition name="v">
    <div class="modal-overlay" v-if="formOpen" @click.self="formOpen = false">
      <div class="co">
        <button class="rv-close" @click="formOpen = false" :aria-label="t('common.close')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
        <h3 class="display rv-form-title">{{ t('reviews.formTitle') }}</h3>
        <p class="a-muted" style="text-align:center">{{ t('reviews.formDesc') }}</p>

        <label class="co-l">{{ t('reviews.ratingLabel') }} *</label>
        <div class="rv-pick" role="radiogroup" :aria-label="t('reviews.ratingLabel')">
          <button
            v-for="n in 5"
            :key="n"
            type="button"
            class="rv-star"
            :class="{ on: n <= form.rating }"
            role="radio"
            :aria-checked="form.rating === n"
            :aria-label="t('reviews.starsAria', { n })"
            @click="form.rating = n"
          >★</button>
        </div>

        <label class="co-l" for="rv-body">{{ t('reviews.bodyLabel') }} *</label>
        <textarea
          id="rv-body"
          class="a-input"
          rows="4"
          :maxlength="BODY_MAX"
          :placeholder="t('reviews.bodyPlaceholder')"
          v-model="form.body"
        ></textarea>
        <p class="a-muted rv-count">{{ t('reviews.remaining', { n: BODY_MAX - form.body.length }) }}</p>

        <label class="co-l" for="rv-city">{{ t('reviews.cityLabel') }}</label>
        <input id="rv-city" class="a-input" v-model.trim="form.city" :placeholder="t('reviews.cityPlaceholder')" :maxlength="CITY_MAX">

        <label class="co-l">{{ t('reviews.photoLabel') }}</label>
        <div class="rv-photo">
          <div v-if="form.image" class="rv-photo-has">
            <img :src="form.image" :alt="t('reviews.photoLabel')">
            <button type="button" class="rv-photo-x" @click="form.image = ''" :aria-label="t('image.remove')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>
            </button>
          </div>
          <button v-else type="button" class="rv-photo-add" :disabled="picking" @click="photoInput?.click()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l5-5 4 4 3-3 6 6"/><circle cx="8.5" cy="7.5" r="1.8"/><rect x="3" y="3" width="18" height="18" rx="3"/></svg>
            <small>{{ picking ? t('image.processing') : t('image.addPhoto') }}</small>
          </button>
          <input ref="photoInput" type="file" accept="image/*" style="display:none" @change="onPhoto">
        </div>

        <p v-if="formErr" class="rv-err">{{ formErr }}</p>
        <button class="btn btn-green rv-submit" :disabled="sending" @click="submit">
          {{ sending ? t('reviews.sending') : t('reviews.submit') }}
        </button>
        <!-- removing the review belongs with editing it, not out on the page -->
        <button v-if="reviews.mine" type="button" class="rv-del" :disabled="sending" @click="removeMine">
          {{ t('reviews.deleteMine') }}
        </button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { useContentStore } from '../stores/content'
import { useReviewsStore } from '../stores/reviews'
import { useToastStore } from '../stores/toast'
import { useConfirmStore } from '../stores/confirm'
import { useAddressesStore } from '../stores/addresses'
import { encodeImageFile } from '../composables/useImageFile'
import Loader from './Loader.vue'
import Stars from './Stars.vue'

// mirrors BODY_MAX / CITY_MAX in backend/routers/reviews.py — the server still
// has the final say, this only keeps the textarea from overrunning it
const BODY_MAX = 600
const CITY_MAX = 60

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const content = useContentStore()
const reviews = useReviewsStore()
const toast = useToastStore()
const confirm = useConfirmStore()
const addresses = useAddressesStore()

const formOpen = ref(false)
const sending = ref(false)
const formErr = ref('')
const form = reactive({ rating: 0, body: '', city: '', image: '' })
const photoInput = ref(null)
const picking = ref(false)

// Downscaled and encoded in the browser (shared with the manager's picker), so the
// upload is a few hundred KB rather than a raw phone photo. The server re-encodes
// and caps it again, and stores it as a file.
async function onPhoto(e) {
  const file = e.target.files?.[0]
  if (!file) return
  picking.value = true
  try {
    form.image = await encodeImageFile(file)
  } catch {
    formErr.value = t('reviews.photoFailed')
  } finally {
    picking.value = false
    if (photoInput.value) photoInput.value.value = '' // let the same file be re-picked
  }
}

// Just the count — "3 آراء". The stars beside it already show the rating, and
// naming the average in words invited more confusion than it cleared up.
// Pluralized through the locale's own rule (six forms in Arabic).
const countLabel = computed(() =>
  t('reviews.reviewCount', { n: reviews.total }, reviews.total))

// Heading copy. Until the manager has saved this section even once, it's the
// bundled translation. After that their version is used verbatim — including a
// field they deliberately emptied, which is how a heading gets removed (clearing
// it can't mean "restore the default", or removing one would be impossible).
// إرجاع النصّ الأصليّ in /manager/content puts the defaults back.
const copy = computed(() => {
  if (!content.sectionSaved('reviews')) {
    return { eyebrow: t('reviews.eyebrow'), title: t('reviews.title'), desc: t('reviews.desc') }
  }
  return content.sectionCopy('reviews', locale.value)
})

const mineNote = computed(() => {
  const s = reviews.mine?.status
  if (!s) return ''
  return s === 'approved' ? t('reviews.mineApproved')
    : s === 'rejected' ? t('reviews.mineRejected')
      : t('reviews.minePending')
})

const initial = (name) => (name || t('reviews.anonymous')).trim().charAt(0)

// Anyone may READ the reviews; writing one needs an account, so the card always
// carries a real customer's name. Guests go to login and come back to '/?review=1',
// which reopens this form — the same trick checkout uses.
async function openForm() {
  if (!auth.isAuthenticated) {
    router.push({ name: 'login', query: { redirect: '/?review=1' } })
    return
  }
  formErr.value = ''
  // returning from login, "mine" may still be in flight — wait, so an existing
  // review prefills the fields instead of opening a blank form over it
  if (!reviews.mineLoaded) await reviews.fetchMine()
  form.rating = reviews.mine?.rating || 0
  form.body = reviews.mine?.body || ''
  form.city = reviews.mine?.city || addresses.default?.city || ''
  form.image = reviews.mine?.image_url || ''
  formOpen.value = true
}
defineExpose({ openForm })

async function submit() {
  formErr.value = ''
  if (!form.rating) { formErr.value = t('reviews.errRating'); return }
  if (form.body.trim().length < 3) { formErr.value = t('reviews.errBody'); return }
  sending.value = true
  try {
    await reviews.submit({
      rating: form.rating,
      body: form.body.trim(),
      city: form.city,
      // an emptied picker clears the photo, since a submit replaces the whole review
      image: form.image || null,
    })
    formOpen.value = false
    toast.show(t('reviews.thanks'), 4000)
  } catch (e) {
    formErr.value = e.message
  } finally {
    sending.value = false
  }
}

async function removeMine() {
  const ok = await confirm.ask({ message: t('reviews.deleteMineMsg'), danger: true })
  if (!ok) return
  try {
    await reviews.remove(reviews.mine.id)
    formOpen.value = false
    toast.show(t('reviews.deleted'))
  } catch (e) {
    toast.show(e.message)
  }
}

onMounted(() => {
  if (!reviews.loaded) reviews.fetch()
  if (!content.loaded) content.fetch() // the heading copy (HomeView usually has it already)
  if (auth.isAuthenticated) {
    reviews.fetchMine()
    // used to prefill the city field; harmless if it fails
    if (!addresses.addresses.length) addresses.fetch().catch(() => {})
  }
})
// signing in or out changes whose review "mine" is
watch(() => auth.isAuthenticated, (signedIn) => {
  if (signedIn) reviews.fetchMine()
  else reviews.clearMine()
})
</script>

<style scoped>
/* The card SHAPE follows the reference design — stars on top, the quote, then a
   round initial disc beside the name and city. The palette stays the storefront's
   own cream and green: the section sits between the value cards and the pantry, so
   a dark block there would cut the page in half. */
.reviews { background: linear-gradient(180deg, var(--paper), var(--cream)); }
.rv-summary {
  display: inline-flex; align-items: center; gap: .6rem; flex-wrap: wrap;
  justify-content: center; margin-top: .8rem;
  font-size: .92rem; font-weight: 700; color: var(--green);
}

.rv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 1.3rem; }
.rv-card {
  display: flex; flex-direction: column; gap: .8rem;
  background: var(--paper); border: 1px solid rgba(60,74,39,.12); border-radius: 20px;
  padding: 1.4rem 1.5rem;
  transition: transform .28s, box-shadow .28s, border-color .28s;
}
.rv-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 30px 50px -34px rgba(44,55,25,.55);
  border-color: rgba(184,144,47,.5);
}
.rv-card blockquote {
  font-family: 'Amiri', serif; font-size: 1.14rem; line-height: 1.75; color: var(--ink);
  flex: 1; white-space: pre-line; overflow-wrap: anywhere;
}
.rv-card footer {
  display: flex; align-items: center; gap: .7rem;
  border-top: 1px solid rgba(60,74,39,.1); padding-top: .8rem;
}
/* the reference puts a round portrait here; we hold no photo, so it's the
   reviewer's initial on a gold disc */
.rv-av {
  flex: 0 0 auto; width: 42px; height: 42px; border-radius: 50%;
  display: grid; place-items: center;
  background: linear-gradient(150deg, var(--gold-2), var(--gold)); color: #fff;
  font-family: 'Amiri', serif; font-size: 1.2rem; font-weight: 700; line-height: 1;
}
.rv-who b { display: block; color: var(--green); font-size: .95rem; }
.rv-who span { font-size: .8rem; color: var(--muted); }
.rv-empty { text-align: center; padding: .6rem 0 0; }
.rv-shot { display: block; border-radius: 14px; overflow: hidden; border: 1px solid rgba(60,74,39,.12); }
.rv-shot img { width: 100%; max-height: 190px; object-fit: cover; transition: transform .4s; }
.rv-shot:hover img { transform: scale(1.04); }

/* photo picker in the form */
.rv-photo { margin-top: .1rem; }
.rv-photo-add {
  display: flex; align-items: center; gap: .5rem;
  width: 100%; padding: .7rem .9rem;
  border: 2px dashed rgba(60,74,39,.3); border-radius: 12px;
  color: var(--green); background: transparent;
}
.rv-photo-add:hover:not(:disabled) { border-color: var(--green); background: rgba(60,74,39,.04); }
.rv-photo-add:disabled { opacity: .6; }
.rv-photo-add svg { width: 20px; height: 20px; }
.rv-photo-add small { font-size: .82rem; font-weight: 700; }
.rv-photo-has { position: relative; border-radius: 12px; overflow: hidden; }
.rv-photo-has img { width: 100%; max-height: 180px; object-fit: cover; display: block; }
.rv-photo-x {
  position: absolute; top: .4rem; inset-inline-end: .4rem;
  width: 28px; height: 28px; border-radius: 50%;
  display: grid; place-items: center;
  background: rgba(0,0,0,.55); color: #fff;
}
.rv-photo-x svg { width: 14px; height: 14px; }

.rv-actions { display: flex; gap: .8rem; justify-content: center; flex-wrap: wrap; margin-top: 2.2rem; }
/* Identical box for both, so the pair reads as a set.
   Width: a flex-basis, not a min-width — with min-width the longer label still wins.
   Height: .btn-gold carries a 2px border and .btn-green carries none, which left the
   outlined button 4px taller; a matching transparent border evens them up. */
.rv-actions .btn { flex: 0 0 var(--cta-w); justify-content: center; }
.rv-actions .btn-green { border: 2px solid transparent; }

.rv-mine {
  margin: 1.1rem auto 0; max-width: 46ch; text-align: center;
  font-size: .86rem; color: var(--green);
  background: rgba(60,74,39,.07); border-radius: 14px; padding: .65rem .9rem;
}
.rv-mine.rejected { color: var(--red); background: rgba(156,43,43,.08); }
/* inside the form, below the submit button — deliberately quiet, since it's the
   destructive option sharing a dialog with the ordinary one */
.rv-del {
  display: block; margin: .7rem auto 0;
  font-size: .82rem; color: var(--muted); text-decoration: underline;
}
.rv-del:hover:not(:disabled) { color: var(--red); }
.rv-del:disabled { opacity: .5; }

/* form modal */
.rv-close {
  position: absolute; top: .8rem; inset-inline-start: .8rem;
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--cream-2); color: var(--green); display: grid; place-items: center;
}
.rv-close:hover { background: var(--gold); color: #fff; }
.rv-close svg { width: 18px; height: 18px; }
.rv-form-title { font-size: 1.6rem; color: var(--green); text-align: center; margin-bottom: .2rem; }
.rv-pick { display: flex; gap: .2rem; justify-content: center; padding: .2rem 0 .4rem; }
.rv-star {
  font-size: 2rem; line-height: 1.1; color: rgba(60,74,39,.22);
  transition: color .15s, transform .15s;
}
.rv-star:hover { transform: scale(1.12); }
.rv-star.on { color: var(--gold); }
.rv-count { text-align: end; font-size: .76rem; margin-top: .2rem; }
.rv-err { color: var(--red); font-size: .85rem; margin-top: .6rem; }
.rv-submit { width: 100%; justify-content: center; margin-top: 1rem; }

@media (max-width: 560px) {
  .rv-grid { grid-template-columns: 1fr; }
  /* full width on a phone — overrides the flex-basis above, which `width` alone can't */
  .rv-actions .btn { flex-basis: 100%; }
}
</style>
