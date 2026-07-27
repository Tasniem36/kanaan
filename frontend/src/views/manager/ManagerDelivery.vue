<template>
  <section>
    <h1>{{ t('manager.deliveryTitle') }}</h1>
    <div class="two-col">
      <!-- global settings + add zone -->
      <div style="align-self:start;display:grid;gap:1rem">
        <div class="a-card">
          <h3 class="ttl">{{ t('manager.deliveryTitle') }}</h3>
          <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.defaultFee') }}</label>
            <input class="a-input" type="number" min="0" step="0.5" v-model.number="g.default_fee"></div>
          <div class="a-field" style="margin-bottom:.3rem"><label>{{ t('manager.freeThreshold') }} <span class='dh' role='img' aria-label='درهم'></span></label>
            <input class="a-input" type="number" min="0" step="1" v-model.number="g.free_threshold"></div>
          <p class="a-muted" style="font-size:.8rem;margin-bottom:.7rem">{{ t('manager.freeThresholdHint') }}</p>
          <button class="a-btn" :disabled="gBusy" @click="saveGlobal">{{ gBusy ? '…' : t('manager.save') }}</button>
        </div>

        <div class="a-card">
          <h3 class="ttl">{{ t('manager.addZone') }}</h3>
          <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.zoneLabel') }} *</label>
            <input class="a-input" v-model.trim="nz.label"></div>
          <div class="a-field" style="margin-bottom:.3rem"><label>{{ t('manager.zoneKeywords') }}</label>
            <input class="a-input" v-model.trim="nz.keywords" placeholder="ابوظبي, abu dhabi, العين"></div>
          <p class="a-muted" style="font-size:.8rem;margin-bottom:.6rem">{{ t('manager.zoneKeywordsHint') }}</p>
          <div class="a-field" style="margin-bottom:.6rem"><label>{{ t('manager.zoneFee') }} *</label>
            <input class="a-input" type="number" min="0" step="0.5" v-model.number="nz.fee"></div>
          <p v-if="nzErr" class="auth-err">{{ nzErr }}</p>
          <button class="a-btn" :disabled="nzBusy" @click="addZone">{{ nzBusy ? '…' : t('manager.addZone') }}</button>
        </div>
      </div>

      <!-- zones list (editable) -->
      <div>
        <h3 class="ttl">{{ t('manager.zonesTitle') }}</h3>
        <p v-if="!forms.length" class="a-muted">{{ t('manager.noZones') }}</p>
        <div v-for="f in forms" :key="f.id" class="a-card" style="margin-bottom:.8rem">
          <div class="a-grid" style="margin-bottom:.5rem">
            <div class="a-field"><label>{{ t('manager.zoneLabel') }}</label><input class="a-input" v-model.trim="f.label"></div>
            <div class="a-field"><label>{{ t('manager.zoneFee') }}</label><input class="a-input" type="number" min="0" step="0.5" v-model.number="f.fee"></div>
          </div>
          <div class="a-field" style="margin-bottom:.5rem"><label>{{ t('manager.zoneKeywords') }}</label><input class="a-input" v-model.trim="f.keywords" dir="auto"></div>
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
import { reactive, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '../../stores/settings'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'

const { t } = useI18n()
const settings = useSettingsStore()
const toast = useToastStore()
const confirm = useConfirmStore()

const g = reactive({ free_threshold: 250, default_fee: 25 })
const gBusy = ref(false)
const nz = reactive({ label: '', keywords: '', fee: '' })
const nzErr = ref('')
const nzBusy = ref(false)
const forms = ref([])

watch(() => settings.delivery, (d) => {
  g.free_threshold = d.free_threshold
  g.default_fee = d.default_fee
  forms.value = (d.zones || []).map((z) => ({ id: z.id, label: z.label, keywords: z.keywords, fee: z.fee, busy: false }))
}, { immediate: true, deep: true })

async function saveGlobal() {
  gBusy.value = true
  try {
    await settings.updateDelivery({ free_threshold: Number(g.free_threshold) || 0, default_fee: Number(g.default_fee) || 0 })
    toast.show(t('manager.deliverySaved'))
  } catch (e) { toast.show(e.message) } finally { gBusy.value = false }
}
async function addZone() {
  nzErr.value = ''
  if (!nz.label || nz.fee === '' || nz.fee === null) { nzErr.value = t('manager.zoneErr'); return }
  nzBusy.value = true
  try {
    await settings.addZone({ label: nz.label, keywords: nz.keywords, fee: Number(nz.fee) || 0 })
    Object.assign(nz, { label: '', keywords: '', fee: '' })
    toast.show(t('manager.toastAdded'))
  } catch (e) { nzErr.value = e.message } finally { nzBusy.value = false }
}
async function saveZone(f) {
  f.busy = true
  try {
    await settings.updateZone(f.id, { label: f.label, keywords: f.keywords, fee: Number(f.fee) || 0 })
    toast.show(t('manager.toastSaved'))
  } catch (e) { toast.show(e.message) } finally { f.busy = false }
}
async function removeZone(f) {
  const ok = await confirm.ask({ title: t('manager.remove'), message: f.label, confirmText: t('manager.remove'), danger: true })
  if (!ok) return
  try { await settings.deleteZone(f.id); toast.show(t('manager.toastRemoved')) }
  catch (e) { toast.show(e.message) }
}

onMounted(() => settings.fetchDelivery())
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.ttl { color: var(--green); font-family: 'Amiri', serif; margin-bottom: .6rem; }
.two-col { display: grid; grid-template-columns: 320px 1fr; gap: 1.2rem; align-items: start; }
@media (max-width: 760px) { .two-col { grid-template-columns: 1fr; } }
.rm-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); cursor: pointer; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin: .4rem 0; }
</style>
