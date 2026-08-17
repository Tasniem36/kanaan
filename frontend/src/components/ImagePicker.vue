<template>
  <div class="imgpick">
    <div class="imgpick-grid">
      <div v-for="(img, i) in list" :key="i" class="imgpick-item" :class="{ primary: i === 0 }">
        <img :src="img" :alt="t('manager.image')">
        <span v-if="i === 0" class="imgpick-badge">{{ t('image.primary') }}</span>
        <div class="imgpick-item-actions">
          <button type="button" v-if="i !== 0" class="ii-btn" :title="t('image.makePrimary')" @click="makePrimary(i)">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.2 4.6 1.5 6.8L12 17.8 5.9 20.4l1.5-6.8L2.2 9l6.9-.7L12 2z"/></svg>
          </button>
          <button type="button" class="ii-btn danger" :title="t('image.remove')" @click="removeAt(i)">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>
          </button>
        </div>
      </div>

      <button type="button" class="imgpick-add" :disabled="busy" @click="fileInput.click()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20"><path d="M12 5v14M5 12h14"/></svg>
        <small>{{ busy ? t('image.processing') : t('image.addPhoto') }}</small>
      </button>
    </div>

    <input ref="fileInput" type="file" accept="image/*" multiple style="display:none" @change="onFiles">

    <details class="imgpick-url">
      <summary>{{ t('image.orUrl') }}</summary>
      <div class="url-row">
        <input class="a-input" v-model.trim="urlInput" placeholder="https://..." dir="ltr" @keyup.enter="addUrl">
        <button type="button" class="a-btn" @click="addUrl" :disabled="!urlInput">+</button>
      </div>
      <div class="chips">
        <button type="button" v-for="img in presets" :key="img.v" class="chip" @click="addImage(img.v)">{{ img.t }}</button>
      </div>
    </details>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue'])

const busy = ref(false)
const fileInput = ref(null)
const urlInput = ref('')

const list = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))

const presets = [
  { v: '/images/oil.jpg', t: 'زيت' }, { v: '/images/zaatar.jpg', t: 'زعتر' },
  { v: '/images/olives.jpg', t: 'زيتون' }, { v: '/images/labneh.jpg', t: 'لبنة' },
  { v: '/images/cheese.jpg', t: 'جبنة' }, { v: '/images/jug.jpg', t: 'إبريق' },
  { v: '/images/cups.jpg', t: 'فناجين' }, { v: '/images/bowl.jpg', t: 'زبديّة' },
]

function commit(next) {
  emit('update:modelValue', next)
}
function addImage(src) {
  if (!src || list.value.includes(src)) return
  commit([...list.value, src])
}
function addUrl() {
  if (!urlInput.value) return
  addImage(urlInput.value)
  urlInput.value = ''
}
function removeAt(i) {
  commit(list.value.filter((_, ix) => ix !== i))
}
function makePrimary(i) {
  const next = [...list.value]
  const [moved] = next.splice(i, 1)
  next.unshift(moved)
  commit(next)
}

// Downscale each picked file to max 1400px and encode it as a compact data URL.
// WebP is ~35% smaller than JPEG at the same visual quality, which is the whole
// upload payload — so a multi-photo product saves noticeably faster on mobile.
// Browsers that can't encode WebP silently hand back a PNG (much *larger*), so
// the result is checked and JPEG used instead.
const MAX_DIM = 1400

function encode(canvas) {
  const webp = canvas.toDataURL('image/webp', 0.85)
  return webp.startsWith('data:image/webp') ? webp : canvas.toDataURL('image/jpeg', 0.82)
}

function processFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > MAX_DIM || height > MAX_DIM) {
          const s = MAX_DIM / Math.max(width, height)
          width = Math.round(width * s)
          height = Math.round(height * s)
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        canvas.getContext('2d').drawImage(img, 0, 0, width, height)
        resolve(encode(canvas))
      }
      img.onerror = reject
      img.src = reader.result
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function onFiles(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  busy.value = true
  try {
    const encoded = await Promise.all(files.map(processFile))
    commit([...list.value, ...encoded])
  } catch {
    /* skip files that fail to decode */
  } finally {
    busy.value = false
    if (fileInput.value) fileInput.value.value = '' // allow re-picking the same file
  }
}
</script>

<style scoped>
.imgpick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 0.5rem;
}
.imgpick-item {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(60, 74, 39, 0.06);
  border: 1px solid rgba(60, 74, 39, 0.12);
}
/* the primary photo gets a large, full preview (whole image, never cropped) */
.imgpick-item.primary {
  border-color: var(--gold, #b8902f);
  grid-column: 1 / -1;
  aspect-ratio: 4 / 3;
}
.imgpick-item img { width: 100%; height: 100%; object-fit: contain; }
.imgpick-badge {
  position: absolute;
  top: 4px;
  inset-inline-start: 4px;
  background: var(--gold, #b8902f);
  color: #fff;
  font-size: 0.62rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 6px;
}
.imgpick-item-actions {
  position: absolute;
  top: 4px;
  inset-inline-end: 4px;
  display: flex;
  gap: 0.25rem;
}
.ii-btn {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
}
.ii-btn:hover { background: rgba(0, 0, 0, 0.8); }
.ii-btn.danger:hover { background: var(--red, #9c2b2b); }
.imgpick-add {
  aspect-ratio: 1 / 1;
  display: grid;
  place-items: center;
  gap: 0.2rem;
  border: 2px dashed rgba(60, 74, 39, 0.3);
  border-radius: 12px;
  color: var(--green, #3c4a27);
  background: transparent;
  cursor: pointer;
  padding: 0.3rem;
}
.imgpick-add small { font-size: 0.7rem; font-weight: 700; text-align: center; line-height: 1.2; }
.imgpick-add:hover:not(:disabled) { border-color: var(--green, #3c4a27); background: rgba(60, 74, 39, 0.04); }
.imgpick-add:disabled { opacity: 0.6; cursor: default; }
.imgpick-url { margin-top: 0.7rem; }
.imgpick-url summary { font-size: 0.82rem; color: var(--green, #3c4a27); cursor: pointer; margin-bottom: 0.4rem; }
.url-row { display: flex; gap: 0.4rem; }
.url-row .a-input { flex: 1; }
.chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem; }
.chip { font-size: 0.75rem; padding: 0.25rem 0.55rem; border-radius: 8px; background: rgba(60, 74, 39, 0.08); color: var(--green, #3c4a27); cursor: pointer; }
.chip:hover { background: rgba(60, 74, 39, 0.16); }
</style>
