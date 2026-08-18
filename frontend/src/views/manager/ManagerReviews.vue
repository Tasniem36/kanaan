<template>
  <section>
    <h1>{{ t('manager.reviewsTitle') }}</h1>

    <nav class="tabs filters">
      <a v-for="f in FILTERS" :key="f.value" :class="{ active: filter === f.value }" @click="filter = f.value">
        {{ t(f.label) }}<span v-if="f.value === 'pending' && reviews.pending" class="nbadge">{{ reviews.pending }}</span>
      </a>
    </nav>

    <Loader v-if="reviews.queueLoading && !reviews.queue.length" :label="t('common.loading')" />
    <p v-else-if="!rows.length" class="a-muted">{{ t('manager.revEmpty') }}</p>

    <div v-else class="cards">
      <article class="a-card rv" v-for="r in rows" :key="r.id">
        <header>
          <Stars :value="r.rating" />
          <span class="pill" :class="r.status">{{ t(`manager.rev${cap(r.status)}`) }}</span>
          <span class="a-muted when">{{ fmt(r.created_at) }}</span>
        </header>
        <p class="body">{{ r.body }}</p>
        <!-- the attached photo is published with the review, so it needs eyes on it too -->
        <a v-if="r.thumb_url || r.image_url" class="shot" :href="r.image_url || r.thumb_url" target="_blank" rel="noopener">
          <img :src="r.thumb_url || r.image_url" :alt="t('reviews.photoLabel')" loading="lazy">
        </a>
        <footer>
          <div class="who">
            <b>{{ r.author || t('reviews.anonymous') }}</b>
            <span class="a-muted" dir="ltr">{{ r.author_email }}<template v-if="r.city"> · {{ r.city }}</template></span>
          </div>
          <div class="acts">
            <button v-if="r.status !== 'approved'" class="a-btn" :disabled="busy === r.id" @click="setStatus(r, 'approved')">{{ t('manager.revApprove') }}</button>
            <button v-if="r.status === 'approved'" class="a-btn ghost" :disabled="busy === r.id" @click="setStatus(r, 'pending')">{{ t('manager.revUnpublish') }}</button>
            <button v-if="r.status !== 'rejected'" class="a-btn ghost" :disabled="busy === r.id" @click="setStatus(r, 'rejected')">{{ t('manager.revReject') }}</button>
            <button class="a-btn danger" :disabled="busy === r.id" @click="remove(r)">{{ t('manager.remove') }}</button>
          </div>
        </footer>
      </article>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReviewsStore } from '../../stores/reviews'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'
import Loader from '../../components/Loader.vue'
import Stars from '../../components/Stars.vue'

const FILTERS = [
  { value: 'pending', label: 'manager.revPending' },
  { value: 'approved', label: 'manager.revApproved' },
  { value: 'rejected', label: 'manager.revRejected' },
  { value: '', label: 'manager.revAll' },
]
const TOAST = { approved: 'manager.revApproveToast', rejected: 'manager.revRejectToast', pending: 'manager.revPendToast' }

const { t, locale } = useI18n()
const reviews = useReviewsStore()
const toast = useToastStore()
const confirm = useConfirmStore()
const filter = ref('pending')
const busy = ref('')

// One fetch of everything, filtered here — the whole queue is small, and this way
// a row stays visible (with its new pill) right after it's approved or rejected.
const rows = computed(() => (filter.value ? reviews.queue.filter((r) => r.status === filter.value) : reviews.queue))

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
const fmt = (d) => new Date(d).toLocaleString(locale.value, { dateStyle: 'medium', timeStyle: 'short' })

async function setStatus(r, status) {
  busy.value = r.id
  try {
    await reviews.setStatus(r.id, status)
    toast.show(t(TOAST[status]))
  } catch (e) {
    toast.show(e.message)
  } finally {
    busy.value = ''
  }
}

async function remove(r) {
  const ok = await confirm.ask({ message: t('manager.revRemoveMsg'), danger: true })
  if (!ok) return
  busy.value = r.id
  try {
    await reviews.remove(r.id)
    toast.show(t('manager.revRemoved'))
  } catch (e) {
    toast.show(e.message)
  } finally {
    busy.value = ''
  }
}

onMounted(() => reviews.fetchQueue().catch(() => { /* session expired — the guard redirects */ }))
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: .8rem; }
.filters { display: inline-flex; margin-bottom: 1.1rem; }
.nbadge {
  display: inline-grid; place-items: center; min-width: 18px; height: 18px; padding: 0 5px;
  margin-inline-start: .35rem; border-radius: 9px;
  background: var(--red); color: #fff; font-size: .72rem; font-weight: 700;
}
.cards { display: grid; gap: .9rem; }
.rv { display: grid; gap: .6rem; }
.rv header { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.rv .when { margin-inline-start: auto; font-size: .78rem; white-space: nowrap; }
.rv .body { white-space: pre-line; overflow-wrap: anywhere; font-size: .95rem; }
.pill { font-size: .72rem; font-weight: 700; padding: .12rem .6rem; border-radius: 999px; background: var(--cream-2); color: var(--green); }
.pill.approved { background: rgba(60,74,39,.14); color: var(--green); }
.pill.pending { background: rgba(184,144,47,.18); color: var(--gold); }
.pill.rejected { background: rgba(156,43,43,.1); color: var(--red); }
.rv footer {
  display: flex; align-items: flex-end; justify-content: space-between; gap: .8rem; flex-wrap: wrap;
  border-top: 1px solid rgba(60,74,39,.1); padding-top: .6rem;
}
.shot { display: block; max-width: 240px; border-radius: 12px; overflow: hidden; border: 1px solid rgba(60,74,39,.14); }
.shot img { width: 100%; max-height: 160px; object-fit: cover; display: block; }
.who b { display: block; color: var(--green); font-size: .92rem; }
.who span { font-size: .78rem; }
.acts { display: flex; gap: .4rem; flex-wrap: wrap; }
.a-btn.ghost { background: var(--cream-2); color: var(--green); }
.a-btn.danger { background: rgba(156,43,43,.1); color: var(--red); }
</style>
