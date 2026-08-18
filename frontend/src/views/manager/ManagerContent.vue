<template>
  <section>
    <h1>{{ t('manager.contentTitle') }}</h1>
    <Loader v-if="content.loading && !forms.length" :label="t('common.loading')" />

    <!-- headings of the customer-reviews section on the homepage -->
    <h2 class="sub">{{ t('manager.secReviews') }}</h2>
    <p class="a-muted hint">{{ t('manager.secHint') }}</p>
    <div class="a-card">
      <label class="sw">
        <input type="checkbox" v-model="sec.shown">
        <span><b>{{ t('manager.secShow') }}</b><br><span class="a-muted">{{ t('manager.secShowHint') }}</span></span>
      </label>
      <div class="grid2">
        <div><label class="co-l">{{ t('manager.vcTitle') }} (ع)</label><input class="a-input" v-model.trim="sec.title_ar"></div>
        <div><label class="co-l">{{ t('manager.vcTitle') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="sec.title_en"></div>
      </div>
      <label class="co-l">{{ t('manager.vcDesc') }} (ع)</label>
      <textarea class="a-input" rows="2" v-model.trim="sec.desc_ar"></textarea>
      <label class="co-l">{{ t('manager.vcDesc') }} (EN)</label>
      <textarea class="a-input" rows="2" dir="ltr" v-model.trim="sec.desc_en"></textarea>
      <div class="acts">
        <button class="a-btn" :disabled="secBusy" @click="saveSection">{{ secBusy ? '…' : t('manager.save') }}</button>
        <button class="a-btn ghost" :disabled="secBusy" @click="resetSection">{{ t('manager.secReset') }}</button>
      </div>
    </div>

    <h2 class="sub">{{ t('manager.secCards') }}</h2>
    <div class="cards">
      <div class="a-card" v-for="f in forms" :key="f.id">
        <div class="c-grid">
          <div class="c-img">
            <label class="co-l">{{ t('manager.vcImage') }}</label>
            <ImagePicker v-model="f.images" />
          </div>
          <div class="c-fields">
            <div class="grid2">
              <div><label class="co-l">{{ t('manager.vcTitle') }} (ع)</label><input class="a-input" v-model.trim="f.title_ar"></div>
              <div><label class="co-l">{{ t('manager.vcTitle') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="f.title_en"></div>
            </div>
            <div class="grid2">
              <div><label class="co-l">{{ t('manager.vcDesc') }} (ع)</label><input class="a-input" v-model.trim="f.desc_ar"></div>
              <div><label class="co-l">{{ t('manager.vcDesc') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="f.desc_en"></div>
            </div>
            <label class="co-l">{{ t('manager.vcMore') }} (ع)</label>
            <textarea class="a-input" rows="2" v-model.trim="f.more_ar"></textarea>
            <label class="co-l">{{ t('manager.vcMore') }} (EN)</label>
            <textarea class="a-input" rows="2" dir="ltr" v-model.trim="f.more_en"></textarea>
            <div style="display:flex;gap:.6rem;margin-top:.7rem">
              <button class="a-btn" :disabled="f.busy" @click="save(f)">{{ f.busy ? '…' : t('manager.save') }}</button>
              <button class="a-btn" style="background:rgba(156,43,43,.1);color:var(--red)" :disabled="f.busy" @click="removeCard(f)">{{ t('manager.remove') }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useContentStore } from '../../stores/content'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'
import ImagePicker from '../../components/ImagePicker.vue'
import Loader from '../../components/Loader.vue'

const SECTION = 'reviews'
const SECTION_FIELDS = ['title_ar', 'title_en', 'desc_ar', 'desc_en']

const { t } = useI18n()
const content = useContentStore()
const toast = useToastStore()
const confirm = useConfirmStore()
const forms = ref([])

// a translation in a specific language, regardless of the dashboard's own locale
const def = (key, lang) => t(key, {}, { locale: lang })

// --- reviews section headings ---
const sec = ref({ ...Object.fromEntries(SECTION_FIELDS.map((f) => [f, ''])), shown: true })
const secBusy = ref(false)

// fill the form once the saved copy arrives (and whenever it changes)
// The built-in wording, per field — what a never-saved section shows.
function bundled(field) {
  const [name, lang] = [field.replace(/_(ar|en)$/, ''), field.endsWith('_ar') ? 'ar' : 'en']
  return def(`reviews.${name}`, lang)
}

// Fill the form with the text that is actually on the page: the manager's saved
// version once it exists, otherwise the built-in wording. Prefilling (rather than
// showing it as a placeholder) is what makes an emptied field mean "remove this
// line" — see the `copy` computed in ReviewsSection.vue.
watch(
  () => content.sections[SECTION],
  (row) => {
    SECTION_FIELDS.forEach((f) => { sec.value[f] = row ? (row[f] || '') : bundled(f) })
    sec.value.shown = !(row || {}).hidden   // stored as `hidden`, shown as a positive switch
  },
  { immediate: true }
)

async function saveSection() {
  secBusy.value = true
  try {
    const { shown, ...copy } = sec.value
    await content.updateSection(SECTION, { ...copy, hidden: !shown })
    toast.show(t('manager.secSaved'))
  } catch (e) {
    toast.show(e.message)
  } finally {
    secBusy.value = false
  }
}

// puts the built-in wording back in every field (leaves the show/hide switch alone)
async function resetSection() {
  const ok = await confirm.ask({ message: t('manager.secResetMsg'), confirmText: t('manager.secReset') })
  if (!ok) return
  SECTION_FIELDS.forEach((f) => { sec.value[f] = bundled(f) })
  await saveSection()
}

// build editable copies whenever the source cards load/change
watch(
  () => content.values,
  (vals) => {
    forms.value = (vals || []).map((v) => ({
      id: v.id,
      title_ar: v.title_ar, title_en: v.title_en,
      desc_ar: v.desc_ar, desc_en: v.desc_en,
      more_ar: v.more_ar, more_en: v.more_en,
      images: v.image_url ? [v.image_url] : [],
      busy: false,
    }))
  },
  { immediate: true }
)

async function removeCard(f) {
  const ok = await confirm.ask({
    title: t('manager.remove'), message: t('manager.vcRemoveMsg'),
    confirmText: t('manager.remove'), danger: true,
  })
  if (!ok) return
  try { await content.deleteValue(f.id); toast.show(t('manager.vcRemoved')) }
  catch (e) { toast.show(e.message) }
}

async function save(f) {
  f.busy = true
  try {
    await content.updateValue(f.id, {
      image_url: f.images[0] || null,
      title_ar: f.title_ar, title_en: f.title_en,
      desc_ar: f.desc_ar, desc_en: f.desc_en,
      more_ar: f.more_ar, more_en: f.more_en,
    })
    toast.show(t('manager.vcSaved'))
  } catch (e) {
    toast.show(e.message)
  } finally {
    f.busy = false
  }
}

content.fetch()
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
h2.sub { font-family: 'Amiri', serif; color: var(--green); font-size: 1.3rem; margin: 1.6rem 0 .2rem; }
.hint { margin-bottom: .6rem; }
.acts { display: flex; gap: .6rem; margin-top: .8rem; }
.sw { display: flex; gap: .6rem; align-items: flex-start; font-size: .9rem; cursor: pointer; margin-bottom: .9rem; }
.sw input { margin-top: .35rem; width: 18px; height: 18px; accent-color: var(--green); }
.sw b { color: var(--green); }
.a-btn.ghost { background: var(--cream-2); color: var(--green); }
.cards { display: grid; gap: 1rem; }
.c-grid { display: grid; grid-template-columns: 220px 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 640px) { .c-grid { grid-template-columns: 1fr; } }
</style>
