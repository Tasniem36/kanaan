<template>
  <section>
    <h1>{{ t('manager.deliveryTitle') }}</h1>
    <div class="two-col">
      <!-- global settings + add a per-emirate fee -->
      <div style="align-self:start;display:grid;gap:1rem">
        <div class="a-card">
          <h3 class="ttl">{{ t('manager.deliveryTitle') }}</h3>
          <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.defaultFee') }}</label>
            <input class="a-input" type="number" min="0" step="0.5" v-model.number="g.default_fee"></div>
          <p class="a-muted" style="font-size:.8rem;margin-bottom:.7rem">{{ t('manager.defaultFeeHint') }}</p>
          <div class="a-field" style="margin-bottom:.3rem"><label>{{ t('manager.freeThreshold') }} <span class='dh' role='img' aria-label='درهم'></span></label>
            <input class="a-input" type="number" min="0" step="1" v-model.number="g.free_threshold"></div>
          <p class="a-muted" style="font-size:.8rem;margin-bottom:.7rem">{{ t('manager.freeThresholdHint') }}</p>
          <button class="a-btn" :disabled="gBusy" @click="saveGlobal">{{ gBusy ? '…' : t('manager.save') }}</button>
        </div>

        <div class="a-card">
          <h3 class="ttl">{{ t('manager.addZone') }}</h3>
          <template v-if="availableEmirates.length">
            <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.zoneEmirate') }} *</label>
              <select class="a-input" v-model="nz.emirate">
                <option value="" disabled>{{ t('checkout.cityPick') }}</option>
                <option v-for="e in availableEmirates" :key="e.value" :value="e.value">{{ locale === 'ar' ? e.value : e.en }}</option>
              </select>
            </div>
            <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.zoneFee') }} *</label>
              <input class="a-input" type="number" min="0" step="0.5" v-model.number="nz.fee"></div>
            <p v-if="nzErr" class="auth-err">{{ nzErr }}</p>
            <button class="a-btn" :disabled="nzBusy" @click="addZone">{{ nzBusy ? '…' : t('manager.addZone') }}</button>
          </template>
          <p v-else class="a-muted" style="font-size:.85rem">{{ t('manager.allEmiratesSet') }}</p>
        </div>
      </div>

      <!-- configured emirates (editable fee) -->
      <div>
        <h3 class="ttl">{{ t('manager.zonesTitle') }}</h3>
        <Loader v-if="loading && !forms.length" :label="t('common.loading')" />
        <p v-else-if="!forms.length" class="a-muted">{{ t('manager.noZones') }}</p>
        <div v-for="f in forms" :key="f.id" class="a-card" style="margin-bottom:.8rem">
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
    </div>
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

const { t, locale } = useI18n()
const settings = useSettingsStore()
const toast = useToastStore()
const confirm = useConfirmStore()

const g = reactive({ free_threshold: 250, default_fee: 25 })
const gBusy = ref(false)
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
    Object.assign(nz, { emirate: '', fee: '' })
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
  try { await settings.fetchDelivery() } finally { loading.value = false }
})
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.ttl { color: var(--green); font-family: 'Amiri', serif; margin-bottom: .6rem; }
.two-col { display: grid; grid-template-columns: 320px 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 760px) { .two-col { grid-template-columns: 1fr; } }
.rm-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); cursor: pointer; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin: .4rem 0; }
</style>
