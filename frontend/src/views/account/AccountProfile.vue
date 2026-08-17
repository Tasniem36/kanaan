<template>
  <section class="panel">
    <div class="panel-head"><h2>{{ t('account.profileTitle') }}</h2></div>
    <form class="prof-form" @submit.prevent="saveProfile">
      <div class="a-grid">
        <div class="a-field"><label>{{ t('account.fullName') }}</label><input class="a-input" v-model.trim="pf.full_name" autocomplete="name"></div>
        <div class="a-field"><label>{{ t('account.phone') }}</label><input class="a-input" type="tel" inputmode="tel" dir="ltr" v-model.trim="pf.phone" placeholder="050 123 4567"></div>
      </div>
      <div class="a-field">
        <label>{{ t('account.email') }}</label>
        <input class="a-input" :value="auth.user?.email" dir="ltr" disabled>
        <small class="a-muted">{{ t('account.emailLocked') }}</small>
      </div>
      <p v-if="profErr" class="auth-err">{{ profErr }}</p>
      <p v-if="profOk" class="prof-ok">✓ {{ t('account.saved') }}</p>
      <button class="a-btn" :disabled="profBusy">{{ profBusy ? '…' : t('account.saveProfile') }}</button>
    </form>
  </section>

  <section class="panel">
    <div class="panel-head"><h2>{{ t('account.addresses') }}</h2></div>
    <Loader v-if="addr.loading && !addr.addresses.length" :label="t('common.loading')" />
    <div v-else-if="addr.addresses.length" class="addr-grid">
      <div class="addr-card" v-for="a in addr.addresses" :key="a.id">
        <div class="addr-top">
          <b>{{ a.label || '—' }}</b>
          <span v-if="a.is_default" class="a-pill pill-ok">{{ t('account.default') }}</span>
        </div>
        <p>{{ t('account.addrLine', { city: a.city, street: a.street, house: a.house }) }}<span v-if="a.notes" class="a-muted"> — {{ a.notes }}</span></p>
        <div class="addr-actions">
          <button v-if="!a.is_default" @click="addr.makeDefault(a.id)">{{ t('account.makeDefault') }}</button>
          <button class="danger" @click="removeAddr(a)">{{ t('account.delete') }}</button>
        </div>
      </div>
    </div>
    <p v-else class="a-muted">{{ t('account.noAddresses') }}</p>

    <form class="addr-form" @submit.prevent="addAddress">
      <div class="a-grid">
        <div class="a-field"><label>{{ t('account.label') }}</label><input class="a-input" v-model.trim="na.label" :placeholder="t('account.labelPh')"></div>
        <div class="a-field"><label>{{ t('account.city') }} *</label>
          <select class="a-input" v-model="na.city">
            <option value="" disabled>{{ t('checkout.cityPick') }}</option>
            <option v-for="e in EMIRATES" :key="e.value" :value="e.value">{{ locale === 'ar' ? e.value : e.en }}</option>
          </select>
        </div>
      </div>
      <div class="a-grid">
        <div class="a-field"><label>{{ t('account.street') }} *</label><input class="a-input" v-model.trim="na.street"></div>
        <div class="a-field"><label>{{ t('account.house') }} *</label><input class="a-input" v-model.trim="na.house"></div>
      </div>
      <div class="a-field"><label>{{ t('account.landmark') }}</label><input class="a-input" v-model.trim="na.notes"></div>
      <label style="display:flex;gap:.4rem;align-items:center;font-size:.85rem"><input type="checkbox" v-model="na.is_default"> {{ t('account.makeDefaultCheck') }}</label>
      <p v-if="addrErr" class="auth-err">{{ addrErr }}</p>
      <button class="a-btn" :disabled="addrBusy">{{ addrBusy ? '…' : t('account.addAddress') }}</button>
    </form>
  </section>
</template>

<script setup>
import { reactive, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAddressesStore } from '../../stores/addresses'
import { useConfirmStore } from '../../stores/confirm'
import { useAuthStore } from '../../stores/auth'
import Loader from '../../components/Loader.vue'
import { EMIRATES } from '../../utils/delivery'
import { normalizeUaePhone } from '../../utils/phone'

const { t, locale } = useI18n()
const addr = useAddressesStore()
const confirm = useConfirmStore()
const auth = useAuthStore()

// profile (name + phone) — email is fixed, verified at signup
const pf = reactive({ full_name: '', phone: '' })
const profErr = ref('')
const profOk = ref(false)
const profBusy = ref(false)
// keep the form in sync with the loaded user (populates once /auth/me resolves)
watch(() => auth.user, (u) => { pf.full_name = u?.full_name || ''; pf.phone = u?.phone || '' }, { immediate: true })

async function saveProfile() {
  profErr.value = ''
  profOk.value = false
  const phone = normalizeUaePhone(pf.phone)
  if (!phone) { profErr.value = t('auth.errPhoneUAE'); return }
  profBusy.value = true
  try {
    await auth.updateProfile({ full_name: pf.full_name, phone })
    profOk.value = true
    setTimeout(() => (profOk.value = false), 2500)
  } catch (e) {
    profErr.value = e.message
  } finally {
    profBusy.value = false
  }
}

const na = reactive({ label: '', city: '', street: '', house: '', notes: '', is_default: false })
const addrErr = ref('')
const addrBusy = ref(false)

async function removeAddr(a) {
  const ok = await confirm.ask({ title: t('account.delete'), message: t('account.addrLine', { city: a.city, street: a.street, house: a.house }), confirmText: t('account.delete'), danger: true })
  if (ok) addr.remove(a.id)
}

async function addAddress() {
  addrErr.value = ''
  if (!na.city || !na.street || !na.house) { addrErr.value = t('account.addrErr'); return }
  addrBusy.value = true
  try {
    await addr.add({ ...na })
    Object.assign(na, { label: '', city: '', street: '', house: '', notes: '', is_default: false })
  } catch (e) {
    addrErr.value = e.message
  } finally {
    addrBusy.value = false
  }
}

onMounted(() => addr.fetch())
</script>

<style scoped>
.panel { background: #fff; border-radius: 18px; padding: 1.4rem; margin-top: 1.4rem; box-shadow: 0 8px 30px rgba(60,74,39,.06); }
.panel-head h2 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.35rem; margin-bottom: .8rem; }
.addr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: .8rem; margin-bottom: 1rem; }
.addr-card { border: 1.5px solid rgba(60,74,39,.15); border-radius: 12px; padding: .8rem; font-size: .9rem; }
.addr-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: .3rem; }
.addr-actions { display: flex; gap: .5rem; margin-top: .6rem; }
.addr-actions button { font-size: .8rem; padding: .3rem .6rem; border-radius: 8px; background: rgba(60,74,39,.08); color: var(--green); cursor: pointer; }
.addr-actions .danger { background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); }
.addr-form { border-top: 1px dashed rgba(60,74,39,.2); padding-top: 1rem; margin-top: .4rem; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; }
.prof-form { display: grid; gap: .4rem; }
.prof-form .a-field { margin-bottom: .4rem; }
.prof-form .a-input:disabled { opacity: .65; cursor: not-allowed; background: var(--cream-2, rgba(60,74,39,.06)); }
.prof-ok { color: var(--green); font-size: .85rem; font-weight: 600; }
</style>
