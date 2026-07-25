<template>
  <section>
    <h1>{{ t('manager.contentTitle') }}</h1>
    <p v-if="content.loaded && !forms.length" class="a-muted">{{ t('common.loading') }}</p>

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

const { t } = useI18n()
const content = useContentStore()
const toast = useToastStore()
const confirm = useConfirmStore()
const forms = ref([])

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
.cards { display: grid; gap: 1rem; }
.c-grid { display: grid; grid-template-columns: 220px 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 640px) { .c-grid { grid-template-columns: 1fr; } }
</style>
