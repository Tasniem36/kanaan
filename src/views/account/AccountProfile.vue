<template>
  <section class="panel">
    <div class="panel-head"><h2>{{ t('account.addresses') }}</h2></div>
    <div v-if="addr.addresses.length" class="addr-grid">
      <div class="addr-card" v-for="a in addr.addresses" :key="a.id">
        <div class="addr-top">
          <b>{{ a.label || '—' }}</b>
          <span v-if="a.is_default" class="a-pill pill-ok">{{ t('account.default') }}</span>
        </div>
        <p>{{ a.city }}، {{ a.street }}، {{ a.house }}<span v-if="a.notes" class="a-muted"> — {{ a.notes }}</span></p>
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
        <div class="a-field"><label>{{ t('account.city') }} *</label><input class="a-input" v-model.trim="na.city"></div>
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
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAddressesStore } from '../../stores/addresses'
import { useConfirmStore } from '../../stores/confirm'

const { t } = useI18n()
const addr = useAddressesStore()
const confirm = useConfirmStore()

const na = reactive({ label: '', city: '', street: '', house: '', notes: '', is_default: false })
const addrErr = ref('')
const addrBusy = ref(false)

async function removeAddr(a) {
  const ok = await confirm.ask({ title: t('account.delete'), message: `${a.city}، ${a.street}، ${a.house}`, confirmText: t('account.delete'), danger: true })
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
</style>
