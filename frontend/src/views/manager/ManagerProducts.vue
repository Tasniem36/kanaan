<template>
  <section>
    <div class="p-head">
      <h1>{{ t('manager.productsTitle') }}</h1>
      <button class="a-btn" :disabled="compressing" @click="compressOld">{{ compressing ? '…' : t('manager.compressImages') }}</button>
    </div>
    <div class="two-col">
      <div class="a-card" style="align-self:start">
        <h3 style="color:var(--green);font-family:'Amiri',serif;margin-bottom:.6rem">{{ t('manager.addProduct') }}</h3>
        <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.name') }} *</label><input class="a-input" v-model.trim="np.name"></div>
        <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.description') }}</label><input class="a-input" v-model.trim="np.description"></div>
        <div class="a-grid" style="margin-bottom:.6rem">
          <div class="a-field"><label>{{ t('manager.category') }}</label><select class="a-select" v-model="np.category"><option value="pantry">{{ t('manager.pantry') }}</option><option value="pottery">{{ t('manager.pottery') }}</option></select></div>
          <div class="a-field"><label>{{ t('manager.unit') }}</label><input class="a-input" v-model.trim="np.unit" placeholder="400غ"></div>
        </div>
        <div class="a-grid" style="margin-bottom:.6rem">
          <div class="a-field"><label>{{ t('manager.price') }} *</label><input class="a-input" type="number" step="0.01" v-model="np.price"></div>
          <div class="a-field"><label>{{ t('manager.stock') }}</label><input class="a-input" type="number" v-model="np.stock"></div>
        </div>
        <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.tag') }}</label>
          <input class="a-input" v-model.trim="np.tag" :placeholder="t('manager.tagPh')" list="tag-presets">
        </div>
        <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.image') }}</label>
          <ImagePicker v-model="np.images" />
        </div>
        <datalist id="tag-presets"><option value="حصاد جديد"></option><option value="الأكثر مبيعًا"></option><option value="يدويّ"></option></datalist>
        <p v-if="pErr" class="auth-err">{{ pErr }}</p>
        <button class="a-btn" :disabled="pBusy" @click="addProduct">{{ pBusy ? '…' : t('manager.addBtn') }}</button>
      </div>

      <div class="table-wrap">
        <table class="a-table">
          <thead><tr><th>{{ t('manager.colProduct') }}</th><th>{{ t('manager.colPrice') }}</th><th class="tc">{{ t('manager.colStock') }}</th><th class="tc">{{ t('manager.colRestock') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in visibleProducts" :key="p.id" :class="{ 'row-hidden': !p.is_active }">
              <td><div class="a-row" style="justify-content:flex-start;gap:.5rem"><img class="a-thumb" :src="p.thumb_url || p.image_url" :alt="p.name"><span style="font-weight:700;color:var(--green)">{{ p.name }}</span><span v-if="!p.is_active" class="a-pill pill-low" style="font-size:.66rem">{{ t('manager.hidden') }}</span></div></td>
              <td>{{ p.price }}</td>
              <td class="tc"><span class="a-pill" :class="p.stock === 0 ? 'pill-low' : (p.stock <= 5 ? 'pill-warn' : 'pill-ok')">{{ p.stock }}</span></td>
              <td class="tc">
                <div class="stock-adjust">
                  <button class="sa-btn" :title="t('manager.decrease')" :disabled="p.stock === 0" @click="doAdjust(p.id, -1)">−</button>
                  <input type="number" min="1" class="a-input sa-qty" v-model.number="restockQty[p.id]" placeholder="1">
                  <button class="sa-btn add" :title="t('manager.increase')" @click="doAdjust(p.id, 1)">+</button>
                </div>
              </td>
              <td style="white-space:nowrap"><button class="ed-btn" @click="toggleActive(p)">{{ p.is_active ? t('manager.hide') : t('manager.show') }}</button> <button class="ed-btn" @click="openEdit(p)">{{ t('manager.edit') }}</button> <button class="rm-btn" @click="removeProduct(p)">{{ t('manager.remove') }}</button></td>
            </tr>
          </tbody>
        </table>
        <Pager v-model="page" :pages="pageCount" />
      </div>
    </div>

    <!-- edit product (incl. image) -->
    <transition name="v">
      <div class="modal-overlay" v-if="editing" @click.self="editing = null">
        <div class="co" style="max-width:520px">
          <button @click="editing = null" aria-label="إغلاق" style="position:absolute;top:.8rem;inset-inline-start:.8rem;width:34px;height:34px;border-radius:10px;background:var(--cream-2);color:var(--green);display:grid;place-items:center"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
          <h3 style="font-family:'Amiri',serif;font-size:1.5rem;color:var(--green);text-align:center;margin-bottom:.8rem">{{ t('manager.editProduct') }}</h3>
          <label class="co-l">{{ t('manager.image') }}</label>
          <ImagePicker v-model="ep.images" />
          <label class="co-l">{{ t('manager.name') }}</label>
          <input class="a-input" v-model.trim="ep.name">
          <label class="co-l">{{ t('manager.description') }}</label>
          <input class="a-input" v-model.trim="ep.description">
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.category') }}</label>
              <select class="a-select" style="width:100%" v-model="ep.category">
                <option value="pantry">{{ t('manager.pantry') }}</option>
                <option value="pottery">{{ t('manager.pottery') }}</option>
              </select>
            </div>
            <div><label class="co-l">{{ t('manager.unit') }}</label><input class="a-input" v-model.trim="ep.unit"></div>
          </div>
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.price') }}</label><input class="a-input" type="number" step="0.01" v-model="ep.price"></div>
            <div><label class="co-l">{{ t('manager.tag') }}</label><input class="a-input" v-model.trim="ep.tag" :placeholder="t('manager.tagPh')" list="tag-presets"></div>
          </div>
          <p v-if="epErr" class="auth-err">{{ epErr }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="epBusy" @click="saveEdit">{{ epBusy ? '…' : t('manager.save') }}</button>
        </div>
      </div>
    </transition>
  </section>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCatalogStore } from '../../stores/catalog'
import { useConfirmStore } from '../../stores/confirm'
import { useToastStore } from '../../stores/toast'
import ImagePicker from '../../components/ImagePicker.vue'
import Pager from '../../components/Pager.vue'
import { shrink } from '../../utils/image'

const { t } = useI18n()
const catalog = useCatalogStore()
const confirm = useConfirmStore()
const toast = useToastStore()

// numbered pagination — 10 products per page
const PER_PAGE = 10
const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(catalog.byStock.length / PER_PAGE)))
const visibleProducts = computed(() => catalog.byStock.slice((page.value - 1) * PER_PAGE, page.value * PER_PAGE))
watch(pageCount, (n) => { if (page.value > n) page.value = n })

const restockQty = reactive({})
const np = reactive({ name: '', description: '', category: 'pantry', unit: '', price: '', stock: '', tag: '', images: [] })
const pErr = ref('')
const pBusy = ref(false)

const editing = ref(null)
const ep = reactive({ name: '', description: '', category: 'pantry', unit: '', price: '', tag: '', images: [] })
const epErr = ref('')
const epBusy = ref(false)

async function addProduct() {
  pErr.value = ''
  if (!np.name || !np.price) { pErr.value = t('manager.errNamePrice'); return }
  pBusy.value = true
  try {
    const thumb_url = await shrink(np.images[0] || null)
    await catalog.create({ ...np, images: [...np.images], thumb_url, price: Number(np.price), stock: Number(np.stock) || 0 })
    Object.assign(np, { name: '', description: '', category: np.category, unit: '', price: '', stock: '', tag: '', images: [] })
    toast.show(t('manager.toastAdded'))
  } catch (e) { pErr.value = e.message } finally { pBusy.value = false }
}
async function doAdjust(id, sign) {
  const qty = Math.abs(Number(restockQty[id]) || 1)
  const delta = sign * qty
  try {
    const p = await catalog.restock(id, delta)
    restockQty[id] = 1
    toast.show(delta > 0 ? t('manager.toastRestocked') : t('manager.toastReduced', { stock: p.stock }))
  } catch (e) { toast.show(e.message) }
}
const compressing = ref(false)
// generate small thumbnails for products uploaded before thumbnails existed
async function compressOld() {
  const targets = catalog.products.filter((p) => !p.thumb_url && (p.image_url || '').startsWith('data:'))
  if (!targets.length) { toast.show(t('manager.compressNone')); return }
  compressing.value = true
  try {
    for (const p of targets) {
      const thumb_url = await shrink(p.image_url)
      await catalog.update(p.id, { thumb_url })
    }
    await catalog.fetch()
    toast.show(t('manager.compressDone', { n: targets.length }))
  } catch (e) {
    toast.show(e.message)
  } finally {
    compressing.value = false
  }
}

async function toggleActive(p) {
  try {
    await catalog.update(p.id, { is_active: !p.is_active })
    toast.show(t('manager.toastSaved'))
  } catch (e) { toast.show(e.message) }
}
async function removeProduct(p) {
  const ok = await confirm.ask({
    title: t('manager.delTitle'),
    message: t('manager.delMsg', { name: p.name }),
    confirmText: t('manager.remove'),
    danger: true,
  })
  if (!ok) return
  try { await catalog.remove(p.id); toast.show(t('manager.toastRemoved')) }
  catch (e) { toast.show(e.message) }
}
async function openEdit(p) {
  epErr.value = ''
  // the list is light (no gallery) — fetch the full product for editing
  let full = p
  try { full = await catalog.fetchOne(p.id) } catch { /* fall back to the light row */ }
  editing.value = full
  const imgs = Array.isArray(full.images) && full.images.length ? [...full.images] : (full.image_url ? [full.image_url] : [])
  Object.assign(ep, { name: full.name, description: full.description || '', category: full.category, unit: full.unit || '', price: full.price, tag: full.tag || '', images: imgs })
}
async function saveEdit() {
  epErr.value = ''
  if (!ep.name || !ep.price) { epErr.value = t('manager.errNamePrice'); return }
  epBusy.value = true
  try {
    const thumb_url = await shrink(ep.images[0] || null)
    await catalog.update(editing.value.id, {
      name: ep.name, description: ep.description, category: ep.category, unit: ep.unit,
      price: Number(ep.price), tag: ep.tag || null, images: [...ep.images], thumb_url,
    })
    editing.value = null
    toast.show(t('manager.toastSaved'))
  } catch (e) { epErr.value = e.message } finally { epBusy.value = false }
}

onMounted(() => catalog.fetch())
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.p-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.p-head h1 { margin-bottom: 0; }
.two-col { display: grid; grid-template-columns: 320px 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 760px) { .two-col { grid-template-columns: 1fr; } }
.rm-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); cursor: pointer; }
.ed-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(60,74,39,.1); color: var(--green, #3c4a27); cursor: pointer; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin: .4rem 0; }
.a-thumb { width: 38px; height: 38px; border-radius: 8px; object-fit: cover; }
.row-hidden td { opacity: .55; }
/* center the Stock badge + the restock stepper in their columns */
.a-table th.tc, .a-table td.tc { text-align: center; }
.tc .stock-adjust { justify-content: center; }
/* stock +/- stepper */
.stock-adjust { display: inline-flex; align-items: center; gap: .3rem; }
.sa-btn {
  width: 30px; height: 30px; flex: 0 0 auto;
  border-radius: 8px; font-size: 1.15rem; font-weight: 700; line-height: 1;
  display: grid; place-items: center;
  background: rgba(60,74,39,.1); color: var(--green, #3c4a27);
}
.sa-btn.add { background: var(--green, #3c4a27); color: #fff; }
.sa-btn:hover:not(:disabled) { filter: brightness(1.08); }
.sa-btn:disabled { opacity: .4; cursor: default; }
.sa-qty { width: 52px; text-align: center; padding-inline: .3rem; }
</style>
