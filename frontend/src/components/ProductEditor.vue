<template>
  <div>
    <label class="co-l">{{ t('manager.image') }}</label>
    <ImagePicker v-model="f.images" />
    <!-- Arabic is the required copy; English is optional and falls back to the
         Arabic wherever it's left blank, so products can be translated over time. -->
    <div class="grid2">
      <div><label class="co-l">{{ t('manager.name') }} (ع) *</label><input class="a-input" v-model.trim="f.name"></div>
      <div><label class="co-l">{{ t('manager.name') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="f.name_en" :placeholder="t('manager.enOptional')"></div>
    </div>
    <div class="grid2">
      <div><label class="co-l">{{ t('manager.description') }} (ع)</label><input class="a-input" v-model.trim="f.description"></div>
      <div><label class="co-l">{{ t('manager.description') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="f.description_en" :placeholder="t('manager.enOptional')"></div>
    </div>
    <div class="grid2">
      <div><label class="co-l">{{ t('manager.category') }}</label>
        <select class="a-select" style="width:100%" v-model="f.category">
          <option value="pantry">{{ t('manager.pantry') }}</option>
          <option value="pottery">{{ t('manager.pottery') }}</option>
        </select>
      </div>
      <div><label class="co-l">{{ t('manager.price') }}</label><input class="a-input" type="number" step="0.01" v-model="f.price"></div>
    </div>
    <div class="grid2">
      <div><label class="co-l">{{ t('manager.unit') }} (ع)</label><input class="a-input" v-model.trim="f.unit"></div>
      <div><label class="co-l">{{ t('manager.unit') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="f.unit_en" :placeholder="t('manager.enOptional')"></div>
    </div>
    <div class="grid2">
      <div><label class="co-l">{{ t('manager.tag') }} (ع)</label><input class="a-input" v-model.trim="f.tag" :placeholder="t('manager.tagPh')" list="pe-tag-presets"></div>
      <div><label class="co-l">{{ t('manager.tag') }} (EN)</label><input class="a-input" dir="ltr" v-model.trim="f.tag_en" :placeholder="t('manager.enOptional')"></div>
    </div>
    <div class="grid2">
      <div><label class="co-l">{{ t('manager.type') }}</label><input class="a-input" v-model.trim="f.type" :placeholder="t('manager.typePh')" list="pe-type-presets"></div>
      <div><label class="co-l">{{ t('manager.order') }}</label><input class="a-input" type="number" v-model="f.sort" :placeholder="t('manager.orderPh')"></div>
    </div>
    <datalist id="pe-tag-presets"><option value="حصاد جديد"></option><option value="الأكثر مبيعًا"></option><option value="يدويّ"></option></datalist>
    <datalist id="pe-type-presets"><option value="مضيفات"></option><option value="صحون"></option><option value="ابريق"></option><option value="اكواب"></option><option value="فناجين"></option><option value="زيت"></option><option value="زعتر"></option><option value="أجبان"></option><option value="ألبان"></option></datalist>
    <p v-if="err" class="auth-err">{{ err }}</p>
    <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="busy" @click="save">{{ busy ? '…' : t('manager.save') }}</button>
  </div>
</template>

<script setup>
// Shared product edit form. Used by the manager Products page and the storefront
// product page so both stay in sync. Stock is intentionally omitted (it's managed
// via restock); this edits the descriptive fields + display order.
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCatalogStore } from '../stores/catalog'
import ImagePicker from './ImagePicker.vue'

const { t } = useI18n()
const catalog = useCatalogStore()
const props = defineProps({ product: { type: Object, required: true } })
const emit = defineEmits(['saved'])

const f = reactive({
  name: '', name_en: '', description: '', description_en: '',
  category: 'pantry', unit: '', unit_en: '', price: '', type: '', tag: '', tag_en: '',
  sort: 0, images: [],
})
const err = ref('')
const busy = ref(false)

function fill(p) {
  const imgs = Array.isArray(p.images) && p.images.length ? [...p.images] : (p.image_url ? [p.image_url] : [])
  Object.assign(f, {
    name: p.name, name_en: p.name_en || '',
    description: p.description || '', description_en: p.description_en || '',
    category: p.category, unit: p.unit || '', unit_en: p.unit_en || '',
    price: p.price, type: p.type || '', tag: p.tag || '', tag_en: p.tag_en || '',
    sort: p.sort ?? 0, images: imgs,
  })
}
fill(props.product)
watch(() => props.product, (p) => { if (p) fill(p) })

async function save() {
  err.value = ''
  if (!f.name || !f.price) { err.value = t('manager.errNamePrice'); return }
  busy.value = true
  try {
    // thumbnail is regenerated server-side when the images change
    await catalog.update(props.product.id, {
      name: f.name, name_en: f.name_en,
      description: f.description, description_en: f.description_en,
      category: f.category, unit: f.unit, unit_en: f.unit_en,
      type: f.type || null, price: Number(f.price), tag: f.tag || null, tag_en: f.tag_en,
      sort: Number(f.sort) || 0, images: [...f.images],
    })
    emit('saved')
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
</script>
