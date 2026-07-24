<template>
  <div class="imgpick">
    <div class="imgpick-preview">
      <img v-if="modelValue" :src="modelValue" :alt="t('manager.image')" @error="broken = true" @load="broken = false">
      <span v-else class="ph">{{ t('image.noImage') }}</span>
      <span v-if="broken && modelValue" class="ph err">{{ t('image.loadError') }}</span>
    </div>

    <div class="imgpick-actions">
      <button type="button" class="up-btn" :disabled="busy" @click="fileInput.click()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><path d="M12 16V4M6 10l6-6 6 6M4 20h16"/></svg>
        {{ busy ? t('image.processing') : t('image.upload') }}
      </button>
      <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFile">
    </div>

    <details class="imgpick-url">
      <summary>{{ t('image.orUrl') }}</summary>
      <input
        class="a-input"
        :value="isDataUrl ? '' : modelValue"
        @input="$emit('update:modelValue', $event.target.value)"
        placeholder="https://..."
        dir="ltr"
      >
      <div class="chips">
        <button type="button" v-for="img in presets" :key="img.v" class="chip" :class="{ on: modelValue === img.v }" @click="$emit('update:modelValue', img.v)">{{ img.t }}</button>
      </div>
    </details>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const props = defineProps({ modelValue: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])

const broken = ref(false)
const busy = ref(false)
const fileInput = ref(null)

const isDataUrl = computed(() => props.modelValue?.startsWith('data:'))

const presets = [
  { v: '/images/oil.jpg', t: 'زيت' }, { v: '/images/zaatar.jpg', t: 'زعتر' },
  { v: '/images/olives.jpg', t: 'زيتون' }, { v: '/images/labneh.jpg', t: 'لبنة' },
  { v: '/images/cheese.jpg', t: 'جبنة' }, { v: '/images/jug.jpg', t: 'إبريق' },
  { v: '/images/cups.jpg', t: 'فناجين' }, { v: '/images/bowl.jpg', t: 'زبديّة' },
]

// Read the chosen file, downscale to max 900px and re-encode as a compact
// JPEG data URL so it stays small enough to store directly.
function onFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  busy.value = true
  broken.value = false
  const reader = new FileReader()
  reader.onload = () => {
    const img = new Image()
    img.onload = () => {
      const max = 900
      let { width, height } = img
      if (width > max || height > max) {
        const s = max / Math.max(width, height)
        width = Math.round(width * s)
        height = Math.round(height * s)
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      canvas.getContext('2d').drawImage(img, 0, 0, width, height)
      emit('update:modelValue', canvas.toDataURL('image/jpeg', 0.82))
      busy.value = false
      if (fileInput.value) fileInput.value.value = '' // allow re-picking same file
    }
    img.onerror = () => { busy.value = false; broken.value = true }
    img.src = reader.result
  }
  reader.onerror = () => { busy.value = false }
  reader.readAsDataURL(file)
}
</script>

<style scoped>
.imgpick-preview {
  width: 100%;
  height: 150px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(60, 74, 39, 0.06);
  display: grid;
  place-items: center;
  margin-bottom: 0.6rem;
  position: relative;
}
.imgpick-preview img { width: 100%; height: 100%; object-fit: cover; }
.ph { color: #9a9c8c; font-size: 0.85rem; }
.ph.err { position: absolute; inset: 0; display: grid; place-items: center; background: rgba(156,43,43,.08); color: var(--red, #9c2b2b); }
.up-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  width: 100%;
  justify-content: center;
  padding: 0.6rem;
  border-radius: 12px;
  background: var(--green, #3c4a27);
  color: #fff;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
}
.up-btn:disabled { opacity: 0.6; cursor: default; }
.imgpick-url { margin-top: 0.6rem; }
.imgpick-url summary { font-size: 0.82rem; color: var(--green, #3c4a27); cursor: pointer; margin-bottom: 0.4rem; }
.chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem; }
.chip { font-size: 0.75rem; padding: 0.25rem 0.55rem; border-radius: 8px; background: rgba(60, 74, 39, 0.08); color: var(--green, #3c4a27); cursor: pointer; }
.chip.on { background: var(--green, #3c4a27); color: #fff; }
</style>
