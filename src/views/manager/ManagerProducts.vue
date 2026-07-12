<template>
  <section>
    <h1>{{ t('manager.productsTitle') }}</h1>
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
        <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.image') }}</label>
          <ImagePicker v-model="np.image_url" />
        </div>
        <p v-if="pErr" class="auth-err">{{ pErr }}</p>
        <button class="a-btn" :disabled="pBusy" @click="addProduct">{{ pBusy ? '…' : t('manager.addBtn') }}</button>
      </div>

      <div class="table-wrap">
        <table class="a-table">
          <thead><tr><th>{{ t('manager.colProduct') }}</th><th>{{ t('manager.colPrice') }}</th><th>{{ t('manager.colStock') }}</th><th>{{ t('manager.colRestock') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in catalog.byStock" :key="p.id">
              <td><div class="a-row" style="justify-content:flex-start;gap:.5rem"><img class="a-thumb" :src="p.image_url" :alt="p.name"><span style="font-weight:700;color:var(--green)">{{ p.name }}</span></div></td>
              <td>{{ p.price }}</td>
              <td><span class="a-pill" :class="p.stock === 0 ? 'pill-low' : (p.stock <= 5 ? 'pill-warn' : 'pill-ok')">{{ p.stock }}</span></td>
              <td>
                <div class="a-row" style="gap:.3rem"><input type="number" min="1" class="a-input" style="width:64px" v-model.number="restockQty[p.id]" placeholder="0"><button class="a-btn" style="padding:.35rem .6rem" @click="doRestock(p.id)">+</button></div>
              </td>
              <td style="white-space:nowrap"><button class="ed-btn" @click="openEdit(p)">{{ t('manager.edit') }}</button> <button class="rm-btn" @click="removeProduct(p)">{{ t('manager.remove') }}</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- edit product (incl. image) -->
    <transition name="v">
      <div class="modal-overlay" v-if="editing" @click.self="editing = null">
        <div class="co" style="max-width:520px">
          <button @click="editing = null" aria-label="إغلاق" style="position:absolute;top:.8rem;inset-inline-start:.8rem;width:34px;height:34px;border-radius:10px;background:var(--cream-2);color:var(--green);display:grid;place-items:center"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
          <h3 style="font-family:'Amiri',serif;font-size:1.5rem;color:var(--green);text-align:center;margin-bottom:.8rem">{{ t('manager.editProduct') }}</h3>
          <label class="co-l">{{ t('manager.image') }}</label>
          <ImagePicker v-model="ep.image_url" />
          <label class="co-l">{{ t('manager.name') }}</label>
          <input class="a-input" v-model.trim="ep.name">
          <label class="co-l">{{ t('manager.description') }}</label>
          <input class="a-input" v-model.trim="ep.description">
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.price') }}</label><input class="a-input" type="number" step="0.01" v-model="ep.price"></div>
            <div><label class="co-l">{{ t('manager.unit') }}</label><input class="a-input" v-model.trim="ep.unit"></div>
          </div>
          <p v-if="epErr" class="auth-err">{{ epErr }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="epBusy" @click="saveEdit">{{ epBusy ? '…' : t('manager.save') }}</button>
        </div>
      </div>
    </transition>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCatalogStore } from '../../stores/catalog'
import { useConfirmStore } from '../../stores/confirm'
import { useToastStore } from '../../stores/toast'
import ImagePicker from '../../components/ImagePicker.vue'

const { t } = useI18n()
const catalog = useCatalogStore()
const confirm = useConfirmStore()
const toast = useToastStore()

const restockQty = reactive({})
const np = reactive({ name: '', description: '', category: 'pantry', unit: '', price: '', stock: '', image_url: '/images/zaatar.jpg' })
const pErr = ref('')
const pBusy = ref(false)

const editing = ref(null)
const ep = reactive({ name: '', description: '', unit: '', price: '', image_url: '' })
const epErr = ref('')
const epBusy = ref(false)

async function addProduct() {
  pErr.value = ''
  if (!np.name || !np.price) { pErr.value = t('manager.errNamePrice'); return }
  pBusy.value = true
  try {
    await catalog.create({ ...np, price: Number(np.price), stock: Number(np.stock) || 0 })
    Object.assign(np, { name: '', description: '', category: np.category, unit: '', price: '', stock: '', image_url: np.image_url })
    toast.show(t('manager.toastAdded'))
  } catch (e) { pErr.value = e.message } finally { pBusy.value = false }
}
async function doRestock(id) {
  const qty = Number(restockQty[id])
  if (!qty || qty <= 0) return
  try { await catalog.restock(id, qty); restockQty[id] = 0; toast.show(t('manager.toastRestocked')) }
  catch (e) { toast.show(e.message) }
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
function openEdit(p) {
  editing.value = p
  epErr.value = ''
  Object.assign(ep, { name: p.name, description: p.description || '', unit: p.unit || '', price: p.price, image_url: p.image_url || '' })
}
async function saveEdit() {
  epErr.value = ''
  if (!ep.name || !ep.price) { epErr.value = t('manager.errNamePrice'); return }
  epBusy.value = true
  try {
    await catalog.update(editing.value.id, {
      name: ep.name, description: ep.description, unit: ep.unit,
      price: Number(ep.price), image_url: ep.image_url,
    })
    editing.value = null
    toast.show(t('manager.toastSaved'))
  } catch (e) { epErr.value = e.message } finally { epBusy.value = false }
}

onMounted(() => catalog.fetch())
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.two-col { display: grid; grid-template-columns: 320px 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 760px) { .two-col { grid-template-columns: 1fr; } }
.rm-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); cursor: pointer; }
.ed-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(60,74,39,.1); color: var(--green, #3c4a27); cursor: pointer; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin: .4rem 0; }
.a-thumb { width: 38px; height: 38px; border-radius: 8px; object-fit: cover; }
</style>
