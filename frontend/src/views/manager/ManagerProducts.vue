<template>
  <section>
    <div class="p-head">
      <h1>{{ t('manager.productsTitle') }}</h1>
      <button class="a-btn" @click="openAdd"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg> {{ t('manager.addProduct') }}</button>
    </div>

    <div class="table-wrap">
      <table class="a-table">
          <thead><tr><th>{{ t('manager.colProduct') }}</th><th>{{ t('manager.colPrice') }}</th><th class="tc">{{ t('manager.colStock') }}</th><th class="tc">{{ t('manager.colRestock') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-if="catalog.loading && !visibleProducts.length"><td colspan="5"><Loader :label="t('common.loading')" /></td></tr>
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
            <tr v-if="hasMore"><td colspan="5"><div ref="sentinel" class="load-more"><span class="ld-spin"></span></div></td></tr>
          </tbody>
        </table>
    </div>

    <!-- shared datalists (used by both the add and edit dialogs) -->
    <datalist id="tag-presets"><option value="حصاد جديد"></option><option value="الأكثر مبيعًا"></option><option value="يدويّ"></option></datalist>
    <datalist id="type-presets"><option value="مضيفات"></option><option value="صحون"></option><option value="ابريق"></option><option value="اكواب"></option><option value="فناجين"></option><option value="زيت"></option><option value="زعتر"></option><option value="أجبان"></option><option value="ألبان"></option></datalist>

    <!-- add product dialog -->
    <Dialog :open="showAdd" :title="t('manager.addProduct')" max-width="520px" @close="showAdd = false">
          <label class="co-l">{{ t('manager.image') }}</label>
          <ImagePicker v-model="np.images" />
          <label class="co-l">{{ t('manager.name') }} *</label>
          <input class="a-input" v-model.trim="np.name">
          <label class="co-l">{{ t('manager.description') }}</label>
          <input class="a-input" v-model.trim="np.description">
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.category') }}</label>
              <select class="a-select" style="width:100%" v-model="np.category">
                <option value="pantry">{{ t('manager.pantry') }}</option>
                <option value="pottery">{{ t('manager.pottery') }}</option>
              </select>
            </div>
            <div><label class="co-l">{{ t('manager.unit') }}</label><input class="a-input" v-model.trim="np.unit" placeholder="400غ"></div>
          </div>
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.price') }} *</label><input class="a-input" type="number" step="0.01" v-model="np.price"></div>
            <div><label class="co-l">{{ t('manager.stock') }}</label><input class="a-input" type="number" v-model="np.stock"></div>
          </div>
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.type') }}</label><input class="a-input" v-model.trim="np.type" :placeholder="t('manager.typePh')" list="type-presets"></div>
            <div><label class="co-l">{{ t('manager.tag') }}</label><input class="a-input" v-model.trim="np.tag" :placeholder="t('manager.tagPh')" list="tag-presets"></div>
          </div>
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.order') }}</label><input class="a-input" type="number" v-model="np.sort" :placeholder="t('manager.orderPh')"></div>
            <div></div>
          </div>
          <p v-if="pErr" class="auth-err">{{ pErr }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="pBusy" @click="addProduct">{{ pBusy ? '…' : t('manager.addBtn') }}</button>
    </Dialog>

    <!-- edit product (incl. image) -->
    <Dialog :open="!!editing" :title="t('manager.editProduct')" max-width="520px" @close="editing = null">
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
            <div><label class="co-l">{{ t('manager.type') }}</label><input class="a-input" v-model.trim="ep.type" :placeholder="t('manager.typePh')" list="type-presets"></div>
          </div>
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.tag') }}</label><input class="a-input" v-model.trim="ep.tag" :placeholder="t('manager.tagPh')" list="tag-presets"></div>
            <div><label class="co-l">{{ t('manager.order') }}</label><input class="a-input" type="number" v-model="ep.sort" :placeholder="t('manager.orderPh')"></div>
          </div>
          <p v-if="epErr" class="auth-err">{{ epErr }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="epBusy" @click="saveEdit">{{ epBusy ? '…' : t('manager.save') }}</button>
    </Dialog>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCatalogStore } from '../../stores/catalog'
import { useConfirmStore } from '../../stores/confirm'
import { useToastStore } from '../../stores/toast'
import ImagePicker from '../../components/ImagePicker.vue'
import Loader from '../../components/Loader.vue'
import Dialog from '../../components/Dialog.vue'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'

const { t } = useI18n()
const catalog = useCatalogStore()
const confirm = useConfirmStore()
const toast = useToastStore()

// infinite scroll — reveal 10 rows, load 10 more on scroll
const { visible: visibleProducts, sentinel, hasMore } = useInfiniteScroll(() => catalog.byStock, 10)

const restockQty = reactive({})
const showAdd = ref(false)
const np = reactive({ name: '', description: '', category: 'pantry', unit: '', price: '', stock: '', type: '', tag: '', sort: '', images: [] })
const pErr = ref('')
const pBusy = ref(false)

function openAdd() {
  pErr.value = ''
  Object.assign(np, { name: '', description: '', category: 'pantry', unit: '', price: '', stock: '', type: '', tag: '', sort: '', images: [] })
  showAdd.value = true
}

const editing = ref(null)
const ep = reactive({ name: '', description: '', category: 'pantry', unit: '', price: '', type: '', tag: '', sort: '', images: [] })
const epErr = ref('')
const epBusy = ref(false)

async function addProduct() {
  pErr.value = ''
  if (!np.name || !np.price) { pErr.value = t('manager.errNamePrice'); return }
  pBusy.value = true
  try {
    // the backend generates the list thumbnail automatically from the first image
    await catalog.create({ ...np, images: [...np.images], price: Number(np.price), stock: Number(np.stock) || 0, sort: Number(np.sort) || 0 })
    showAdd.value = false
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
  Object.assign(ep, { name: full.name, description: full.description || '', category: full.category, unit: full.unit || '', price: full.price, type: full.type || '', tag: full.tag || '', sort: full.sort ?? 0, images: imgs })
}
async function saveEdit() {
  epErr.value = ''
  if (!ep.name || !ep.price) { epErr.value = t('manager.errNamePrice'); return }
  epBusy.value = true
  try {
    // thumbnail is regenerated server-side when the images change
    await catalog.update(editing.value.id, {
      name: ep.name, description: ep.description, category: ep.category, unit: ep.unit,
      type: ep.type || null, price: Number(ep.price), tag: ep.tag || null, sort: Number(ep.sort) || 0, images: [...ep.images],
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
