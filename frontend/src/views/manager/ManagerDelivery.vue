<template>
  <section>
    <div class="p-head">
      <h1>{{ t('manager.deliveryTitle') }}</h1>
      <button v-if="availableEmirates.length" class="a-btn" @click="openAdd"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg> {{ t('manager.addZone') }}</button>
    </div>

    <!-- checkout policy -->
    <div class="a-card" style="max-width:520px;margin-bottom:1.4rem">
      <h3 class="ttl">{{ t('manager.checkoutTitle') }}</h3>
      <label class="sw">
        <input type="checkbox" v-model="guestAllowed">
        <span><b>{{ t('manager.guestAllowed') }}</b><br><span class="a-muted">{{ t('manager.guestAllowedHint') }}</span></span>
      </label>
      <button class="a-btn" :disabled="cBusy" @click="saveCheckout">{{ cBusy ? '…' : t('manager.save') }}</button>
    </div>

    <!-- global settings -->
    <div class="a-card" style="max-width:520px;margin-bottom:1.4rem">
      <h3 class="ttl">{{ t('manager.deliveryTitle') }}</h3>
      <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.defaultFee') }}</label>
        <input class="a-input" type="number" min="0" step="0.5" v-model.number="g.default_fee"></div>
      <p class="a-muted" style="font-size:.8rem;margin-bottom:.7rem">{{ t('manager.defaultFeeHint') }}</p>
      <div class="a-field" style="margin-bottom:.3rem"><label>{{ t('manager.freeThreshold') }} <span class='dh' role='img' aria-label='درهم'></span></label>
        <input class="a-input" type="number" min="0" step="1" v-model.number="g.free_threshold"></div>
      <p class="a-muted" style="font-size:.8rem;margin-bottom:.7rem">{{ t('manager.freeThresholdHint') }}</p>
      <button class="a-btn" :disabled="gBusy" @click="saveGlobal">{{ gBusy ? '…' : t('manager.save') }}</button>
    </div>

    <!-- configured emirates (editable fee) -->
    <h3 class="ttl">{{ t('manager.zonesTitle') }}</h3>
    <Loader v-if="loading && !forms.length" :label="t('common.loading')" />
    <p v-else-if="!forms.length" class="a-muted">{{ t('manager.noZones') }}</p>
    <div v-else class="zones-grid">
      <div v-for="f in forms" :key="f.id" class="a-card">
        <div class="a-grid" style="margin-bottom:.5rem">
          <div class="a-field"><label>{{ t('manager.zoneEmirate') }}</label><input class="a-input" :value="emirateLabel(f)" disabled></div>
          <div class="a-field"><label>{{ t('manager.zoneFee') }}</label><input class="a-input" type="number" min="0" step="0.5" v-model.number="f.fee"></div>
        </div>
        <div style="display:flex;gap:.6rem">
          <button class="a-btn" :disabled="f.busy" @click="saveZone(f)">{{ f.busy ? '…' : t('manager.save') }}</button>
          <button class="rm-btn" @click="removeZone(f)">{{ t('manager.remove') }}</button>
        </div>
      </div>
    </div>

    <!-- add emirate fee dialog -->
    <Dialog :open="showAdd" :title="t('manager.addZone')" max-width="420px" @close="showAdd = false">
          <label class="co-l">{{ t('manager.zoneEmirate') }} *</label>
          <select class="a-input" v-model="nz.emirate">
            <option value="" disabled>{{ t('checkout.cityPick') }}</option>
            <option v-for="e in availableEmirates" :key="e.value" :value="e.value">{{ locale === 'ar' ? e.value : e.en }}</option>
          </select>
          <label class="co-l" style="margin-top:.6rem">{{ t('manager.zoneFee') }} *</label>
          <input class="a-input" type="number" min="0" step="0.5" v-model.number="nz.fee">
          <p v-if="nzErr" class="auth-err">{{ nzErr }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="nzBusy" @click="addZone">{{ nzBusy ? '…' : t('manager.addZone') }}</button>
    </Dialog>
  </section>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '../../stores/settings'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'
import { EMIRATES } from '../../utils/delivery'
import Loader from '../../components/Loader.vue'
import Dialog from '../../components/Dialog.vue'

const { t, locale } = useI18n()
const settings = useSettingsStore()
const toast = useToastStore()
const confirm = useConfirmStore()

const g = reactive({ free_threshold: 250, default_fee: 25 })
const gBusy = ref(false)

// checkout policy: ordering without an account, off unless the manager allows it
const guestAllowed = ref(false)
const cBusy = ref(false)
watch(() => settings.checkout.guest_allowed, (v) => { guestAllowed.value = !!v }, { immediate: true })

async function saveCheckout() {
  cBusy.value = true
  try {
    await settings.updateCheckout({ guest_allowed: guestAllowed.value })
    toast.show(t('manager.checkoutSaved'))
  } catch (e) {
    toast.show(e.message)
  } finally {
    cBusy.value = false
  }
}
const showAdd = ref(false)
const nz = reactive({ emirate: '', fee: '' })
const nzErr = ref('')
const nzBusy = ref(false)
const forms = ref([])
const loading = ref(false)

// each zone is bound to one emirate; the canonical name lives in `keywords`
// (matched verbatim against the customer's dropdown choice at checkout)
watch(() => settings.delivery, (d) => {
  g.free_threshold = d.free_threshold
  g.default_fee = d.default_fee
  forms.value = (d.zones || []).map((z) => ({
    id: z.id, fee: z.fee, busy: false,
    emirate: (z.keywords || z.label || '').trim(),
  }))
}, { immediate: true, deep: true })

function emirateLabel(f) {
  const e = EMIRATES.find((x) => x.value === f.emirate)
  return e ? (locale.value === 'ar' ? e.value : e.en) : f.emirate
}
// emirates that don't have a fee yet
const availableEmirates = computed(() => {
  const taken = new Set(forms.value.map((f) => f.emirate))
  return EMIRATES.filter((e) => !taken.has(e.value))
})

function openAdd() {
  nzErr.value = ''
  Object.assign(nz, { emirate: '', fee: '' })
  showAdd.value = true
}

async function saveGlobal() {
  gBusy.value = true
  try {
    await settings.updateDelivery({ free_threshold: Number(g.free_threshold) || 0, default_fee: Number(g.default_fee) || 0 })
    toast.show(t('manager.deliverySaved'))
  } catch (e) { toast.show(e.message) } finally { gBusy.value = false }
}
async function addZone() {
  nzErr.value = ''
  if (!nz.emirate || nz.fee === '' || nz.fee === null) { nzErr.value = t('manager.zoneErr'); return }
  nzBusy.value = true
  try {
    // label + keywords both hold the canonical emirate name
    await settings.addZone({ label: nz.emirate, keywords: nz.emirate, fee: Number(nz.fee) || 0 })
    showAdd.value = false
    toast.show(t('manager.toastAdded'))
  } catch (e) { nzErr.value = e.message } finally { nzBusy.value = false }
}
async function saveZone(f) {
  f.busy = true
  try {
    await settings.updateZone(f.id, { fee: Number(f.fee) || 0 })
    toast.show(t('manager.toastSaved'))
  } catch (e) { toast.show(e.message) } finally { f.busy = false }
}
async function removeZone(f) {
  const ok = await confirm.ask({ title: t('manager.remove'), message: emirateLabel(f), confirmText: t('manager.remove'), danger: true })
  if (!ok) return
  try { await settings.deleteZone(f.id); toast.show(t('manager.toastRemoved')) }
  catch (e) { toast.show(e.message) }
}

onMounted(async () => {
  loading.value = true
  settings.fetchCheckout() // fills the guest-checkout switch
  try { await settings.fetchDelivery() } finally { loading.value = false }
})
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.p-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.p-head h1 { margin-bottom: 0; }
.sw { display: flex; gap: .6rem; align-items: flex-start; font-size: .9rem; cursor: pointer; margin-bottom: .9rem; }
.sw input { margin-top: .35rem; width: 18px; height: 18px; accent-color: var(--green); }
.sw b { color: var(--green); }
.ttl { color: var(--green); font-family: 'Amiri', serif; margin-bottom: .6rem; }
.zones-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: .8rem; align-items: start; }
.rm-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); cursor: pointer; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin: .4rem 0; }
</style>
