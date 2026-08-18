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
          <!-- the exact average, not a rounded one: the number beside it says 4.6,
               so the stars must not show five -->
          <Stars :value="reviews.average || 0" />
          <span>{{ summary }}</span>
        </div>
      </div>

      <Loader v-if="reviews.loading && !reviews.list.length" />

      <div v-else-if="reviews.list.length" class="rv-grid">
        <article class="rv-card reveal" v-for="r in reviews.list" :key="r.id">
          <Stars :value="r.rating" />
          <blockquote>“{{ r.body }}”</blockquote>
          <footer>
            <!-- the reference design puts a round portrait here; we hold no photo
                 or country for a reviewer, so it's their initial on a gold disc -->
            <span class="rv-av" aria-hidden="true">{{ initial(r.author) }}</span>
            <div class="rv-who">
              <b>{{ r.author || t('reviews.anonymous') }}</b>
              <span v-if="r.city">{{ r.city }}</span>
            </div>
            <time :datetime="r.created_at">{{ shortDate(r.created_at) }}</time>
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

      <!-- where the customer's own review stands (only they see this) -->
      <p v-if="mineNote" class="rv-mine" :class="reviews.mine.status">
        {{ mineNote }}
        <button class="rv-del" @click="removeMine">{{ t('reviews.deleteMine') }}</button>
      </p>
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

        <p v-if="formErr" class="rv-err">{{ formErr }}</p>
        <button class="btn btn-green rv-submit" :disabled="sending" @click="submit">
          {{ sending ? t('reviews.sending') : t('reviews.submit') }}
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
const form = reactive({ rating: 0, body: '', city: '' })

// "4.5 out of 5 · 12 reviews" — the count is pluralized separately so the average
// clause isn't repeated once per Arabic plural form.
//
// With a single review there is no average to speak of, so that wording drops out:
// "متوسّط 5 من 5 · رأيٌ واحد" claims a statistic that doesn't exist yet.
const summary = computed(() => t(reviews.total === 1 ? 'reviews.summaryOne' : 'reviews.summary', {
  avg: reviews.average,
  count: t('reviews.reviewCount', { n: reviews.total }, reviews.total),
}))

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

function shortDate(iso) {
  try {
    return new Date(iso).toLocaleDateString(locale.value === 'ar' ? 'ar-AE' : 'en-GB',
      { year: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}

// Writing needs an account (the card carries the customer's name). Send guests to
// login and back to '/?review=1', which reopens this form — same trick checkout uses.
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
  formOpen.value = true
}
defineExpose({ openForm })

async function submit() {
  formErr.value = ''
  if (!form.rating) { formErr.value = t('reviews.errRating'); return }
  if (form.body.trim().length < 3) { formErr.value = t('reviews.errBody'); return }
  sending.value = true
  try {
    await reviews.submit({ rating: form.rating, body: form.body.trim(), city: form.city })
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
/* Dark section, per the reference design: near-black ground, gold accents, and
   quote cards that sit slightly lighter than the background. Deliberately the
   only dark block on the cream storefront, so the reviews read as a break. */
.reviews {
  --rv-ink: #12120f;      /* section ground */
  --rv-card: #1c1c17;     /* card ground, a touch lighter */
  --rv-line: rgba(255,255,255,.09);
  --rv-text: #f6f2e8;
  --rv-mut: rgba(246,242,232,.6);
  background: var(--rv-ink);
  color: var(--rv-text);
}
/* the global .sec-head is written for the cream sections — repaint it here */
.reviews .sec-head h2 { color: var(--rv-text); }
.reviews .sec-head p { color: var(--rv-mut); }
/* eyebrow becomes a pill; the global rule draws flanking rules we don't want */
.reviews .eyebrow {
  background: rgba(205,169,79,.14);
  color: var(--gold-2);
  padding: .3rem .95rem;
  border-radius: 999px;
}
.reviews .eyebrow::before, .reviews .eyebrow::after { display: none; }
.rv-summary {
  display: inline-flex; align-items: center; gap: .6rem; flex-wrap: wrap;
  justify-content: center; margin-top: .9rem;
  font-size: .92rem; font-weight: 700; color: var(--gold-2);
}

.rv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 1.3rem; }
.rv-card {
  display: flex; flex-direction: column; gap: .9rem;
  background: var(--rv-card); border: 1px solid var(--rv-line); border-radius: 20px;
  padding: 1.4rem 1.5rem;
  transition: transform .28s, box-shadow .28s, border-color .28s;
}
.rv-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 30px 50px -30px #000;
  border-color: rgba(205,169,79,.45);
}
.rv-card blockquote {
  font-family: 'Amiri', serif; font-size: 1.14rem; line-height: 1.75; color: var(--rv-text);
  flex: 1; white-space: pre-line; overflow-wrap: anywhere;
}
.rv-card footer {
  display: flex; align-items: center; gap: .7rem;
  border-top: 1px solid var(--rv-line); padding-top: .8rem;
}
.rv-av {
  flex: 0 0 auto; width: 42px; height: 42px; border-radius: 50%;
  display: grid; place-items: center;
  background: linear-gradient(150deg, var(--gold), #8a6a1f); color: #12120f;
  font-family: 'Amiri', serif; font-size: 1.2rem; font-weight: 700; line-height: 1;
}
.rv-who b { display: block; color: var(--rv-text); font-size: .95rem; }
.rv-who span { font-size: .8rem; color: var(--rv-mut); }
.rv-card time { margin-inline-start: auto; font-size: .74rem; color: var(--rv-mut); white-space: nowrap; }
.rv-empty { text-align: center; padding: .6rem 0 0; color: var(--rv-mut); }

.rv-actions { display: flex; gap: .8rem; justify-content: center; flex-wrap: wrap; margin-top: 2.2rem; }
/* Identical fixed width for both, so the pair reads as a set. A flex-basis (not
   min-width) is what actually equalises them — with min-width, the longer label
   still wins and they end up different sizes. */
.rv-actions .btn { flex: 0 0 13.5rem; justify-content: center; }
/* the cream-section button colours have too little contrast here: gold fill for
   the primary action, gold outline for the secondary */
.rv-actions .btn-green { background: var(--gold); color: #12120f; box-shadow: 0 16px 30px -18px #000; }
.rv-actions .btn-green:hover { background: var(--gold-2); }
.rv-actions .btn-gold { border-color: rgba(205,169,79,.5); color: var(--gold-2); }
.rv-actions .btn-gold:hover { background: var(--gold-2); color: #12120f; }

.rv-mine {
  margin: 1.1rem auto 0; max-width: 46ch; text-align: center;
  font-size: .86rem; color: var(--rv-text);
  background: rgba(255,255,255,.06); border-radius: 14px; padding: .65rem .9rem;
}
.rv-mine.rejected { color: #e79a9a; background: rgba(231,154,154,.1); }
.rv-del {
  display: block; margin: .3rem auto 0;
  font-size: .78rem; color: var(--rv-mut); text-decoration: underline;
}
.rv-del:hover { color: #e79a9a; }

/* form modal — a root-level sibling, so it keeps the cream styling of every other
   dialog on the site rather than the dark section's */
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
