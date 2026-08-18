<template>
  <!-- Hidden until a review is approved (see the store's `visible` getter). The
       component itself always mounts, so the fetch that decides this still runs. -->
  <section v-if="reviews.visible" class="reviews" id="reviews">
    <div class="wrap">
      <div class="sec-head reveal">
        <span class="eyebrow">{{ copy.eyebrow }}</span>
        <h2 class="display">{{ copy.title }}</h2>
        <p>{{ copy.desc }}</p>
        <div v-if="reviews.total" class="rv-summary">
          <Stars :value="Math.round(reviews.average || 0)" />
          <span>{{ t('reviews.summary', { avg: reviews.average, n: reviews.total }) }}</span>
        </div>
      </div>

      <Loader v-if="reviews.loading && !reviews.list.length" />

      <div v-else-if="reviews.list.length" class="rv-grid">
        <article class="rv-card reveal" v-for="r in reviews.list" :key="r.id">
          <Stars :value="r.rating" />
          <blockquote>“{{ r.body }}”</blockquote>
          <footer>
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
          {{ reviews.loading ? t('common.loading') : t('reviews.showMore') }}
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

// Heading copy: whatever the manager typed in /manager/content wins; each field
// they left blank falls back to the bundled translation.
const copy = computed(() => {
  const edited = content.sectionCopy('reviews', locale.value)
  return {
    eyebrow: edited.eyebrow || t('reviews.eyebrow'),
    title: edited.title || t('reviews.title'),
    desc: edited.desc || t('reviews.desc'),
  }
})

const mineNote = computed(() => {
  const s = reviews.mine?.status
  if (!s) return ''
  return s === 'approved' ? t('reviews.mineApproved')
    : s === 'rejected' ? t('reviews.mineRejected')
      : t('reviews.minePending')
})

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
.reviews { background: linear-gradient(180deg, var(--paper), var(--cream)); }
.rv-summary {
  display: inline-flex; align-items: center; gap: .6rem; flex-wrap: wrap;
  justify-content: center; margin-top: .7rem;
  font-size: .92rem; font-weight: 700; color: var(--green);
}
.rv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 1.3rem; }
.rv-card {
  display: flex; flex-direction: column; gap: .7rem;
  background: var(--paper); border: 1px solid rgba(60,74,39,.12); border-radius: 20px;
  padding: 1.3rem 1.4rem;
  transition: transform .28s, box-shadow .28s, border-color .28s;
}
.rv-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 30px 50px -34px rgba(44,55,25,.55);
  border-color: rgba(184,144,47,.5);
}
.rv-card blockquote {
  font-family: 'Amiri', serif; font-size: 1.12rem; line-height: 1.7; color: var(--ink);
  flex: 1; white-space: pre-line; overflow-wrap: anywhere;
}
.rv-card footer {
  display: flex; align-items: flex-end; justify-content: space-between; gap: .6rem;
  border-top: 1px solid rgba(60,74,39,.1); padding-top: .7rem;
}
.rv-who b { display: block; color: var(--green); font-size: .95rem; }
.rv-who span { font-size: .8rem; color: var(--muted); }
.rv-card time { font-size: .76rem; color: var(--muted); white-space: nowrap; }
.rv-empty { text-align: center; padding: .6rem 0 0; }
.rv-actions { display: flex; gap: .8rem; justify-content: center; flex-wrap: wrap; margin-top: 2rem; }
/* both buttons share one width, so the pair reads as a set however long the labels are */
.rv-actions .btn { min-width: 13.5rem; justify-content: center; }
.rv-mine {
  margin: 1rem auto 0; max-width: 46ch; text-align: center;
  font-size: .86rem; color: var(--green);
  background: rgba(60,74,39,.07); border-radius: 14px; padding: .6rem .9rem;
}
.rv-mine.rejected { color: var(--red); background: rgba(156,43,43,.08); }
.rv-del {
  display: block; margin: .3rem auto 0;
  font-size: .78rem; color: var(--muted); text-decoration: underline;
}
.rv-del:hover { color: var(--red); }

/* form */
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
  .rv-actions .btn { width: 100%; justify-content: center; }
}
</style>
