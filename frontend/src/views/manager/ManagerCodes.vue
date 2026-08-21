<template>
  <section>
    <div class="p-head">
      <h1>{{ t('manager.codesTitle') }}</h1>
      <button class="a-btn" @click="openAdd"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg> {{ t('manager.codeAddTitle') }}</button>
    </div>

    <div class="table-wrap">
      <Loader v-if="loading && !codes.length" :label="t('common.loading')" />
      <p v-else-if="!codes.length" class="a-muted">{{ t('manager.noCodes') }}</p>
      <table v-else class="a-table">
        <thead><tr><th>{{ t('manager.codeLabel') }}</th><th>{{ t('manager.codeValue') }}</th><th>{{ t('manager.colFirstOrder') }}</th><th>{{ t('manager.codeUses') }}</th><th>{{ t('manager.colActive') }}</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in codes" :key="c.id">
            <td style="font-family:monospace;font-weight:700;color:var(--green)">{{ c.code }}</td>
            <td v-if="c.percent">{{ c.percent }}%</td>
            <td v-else style="white-space:nowrap">{{ money(c.amount) }} <span class="dh" role="img" aria-label="درهم"></span></td>
            <td>{{ c.first_order_only ? '✓' : '—' }}</td>
            <td>{{ c.used_count }}<span v-if="c.max_uses">/{{ c.max_uses }}</span></td>
            <td>
              <button class="a-pill" :class="c.active ? 'pill-ok' : 'pill-low'" @click="toggle(c)">{{ c.active ? t('manager.codeActive') : '—' }}</button>
            </td>
            <td><button class="rm-btn" @click="remove(c)">{{ t('manager.remove') }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- add code dialog -->
    <Dialog :open="showAdd" :title="t('manager.codeAddTitle')" max-width="460px" @close="showAdd = false">
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.codeLabel') }} *</label><input class="a-input" v-model.trim="nc.code" dir="ltr" style="text-align:start;text-transform:uppercase"></div>
            <div>
              <!-- the label names whichever kind is selected, so the number in the
                   box beside it is never ambiguous -->
              <label class="co-l">{{ nc.kind === 'percent' ? t('manager.codePercent') : t('manager.codeAmount') }} *</label>
              <div class="kind-row">
                <div class="kind-pick">
                  <button type="button" :class="{ on: nc.kind === 'percent' }" @click="nc.kind = 'percent'">%</button>
                  <button type="button" :class="{ on: nc.kind === 'amount' }" @click="nc.kind = 'amount'"><span class="dh" role="img" aria-label="درهم"></span></button>
                </div>
                <input class="a-input" type="number" min="1" :max="nc.kind === 'percent' ? 100 : null"
                       :step="nc.kind === 'percent' ? 1 : 0.5" v-model="nc.value" dir="ltr">
              </div>
              <small class="kind-hint">{{ nc.kind === 'percent' ? t('manager.codeHintPercent') : t('manager.codeHintAmount') }}</small>
            </div>
          </div>
          <div class="grid2">
            <div><label class="co-l">{{ t('manager.codeMaxUses') }}</label><input class="a-input" type="number" min="1" v-model="nc.max_uses"></div>
            <div><label class="co-l">{{ t('manager.codeExpiry') }}</label><input class="a-input" type="date" v-model="nc.expires_at"></div>
          </div>
          <label style="display:flex;gap:.4rem;align-items:center;font-size:.88rem;margin-top:.6rem"><input type="checkbox" v-model="nc.first_order_only"> {{ t('manager.codeFirstOrder') }}</label>
          <label style="display:flex;gap:.4rem;align-items:center;font-size:.88rem;margin-top:.4rem"><input type="checkbox" v-model="nc.active"> {{ t('manager.codeActive') }}</label>
          <p v-if="err" class="auth-err">{{ err }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="busy" @click="addCode">{{ busy ? '…' : t('manager.codeAdd') }}</button>
    </Dialog>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'
import Loader from '../../components/Loader.vue'
import Dialog from '../../components/Dialog.vue'

const { t } = useI18n()
const toast = useToastStore()
const confirm = useConfirmStore()

const codes = ref([])
const showAdd = ref(false)
// `kind` picks which sort of discount `value` is: a percentage off, or dirhams off
const BLANK = { code: '', kind: 'percent', value: '', max_uses: '', expires_at: '', first_order_only: true, active: true }
const nc = reactive({ ...BLANK })
const err = ref('')
const busy = ref(false)
const loading = ref(false)

const money = (n) => Math.round(Number(n) * 100) / 100

function openAdd() {
  err.value = ''
  Object.assign(nc, BLANK)
  showAdd.value = true
}

async function load() {
  loading.value = true
  try {
    const { codes: c } = await api('/discounts')
    codes.value = c
  } finally {
    loading.value = false
  }
}
async function addCode() {
  err.value = ''
  if (!nc.code || !nc.value) { err.value = t('manager.codeErr'); return }
  busy.value = true
  try {
    await api('/discounts', { method: 'POST', body: {
      code: nc.code,
      // only the chosen one is sent — the server refuses a code carrying both
      [nc.kind]: Number(nc.value),
      first_order_only: nc.first_order_only, active: nc.active,
      max_uses: nc.max_uses ? Number(nc.max_uses) : null,
      expires_at: nc.expires_at || null,
    } })
    showAdd.value = false
    toast.show(t('manager.toastCodeAdded'))
    await load()
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
async function toggle(c) {
  try { await api(`/discounts/${c.id}`, { method: 'PATCH', body: { active: !c.active } }); await load() }
  catch (e) { toast.show(e.message) }
}
async function remove(c) {
  const ok = await confirm.ask({ title: t('manager.remove'), message: c.code, confirmText: t('manager.remove'), danger: true })
  if (!ok) return
  try { await api(`/discounts/${c.id}`, { method: 'DELETE' }); toast.show(t('manager.toastCodeRemoved')); await load() }
  catch (e) { toast.show(e.message) }
}

onMounted(load)
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.p-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
.p-head h1 { margin-bottom: 0; }
.rm-btn { font-size: .82rem; padding: .35rem .7rem; border-radius: 8px; background: rgba(156,43,43,.1); color: var(--red, #9c2b2b); cursor: pointer; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin: .4rem 0; }
.a-pill { cursor: pointer; border: none; }
/* percentage-or-dirhams picker sitting beside the number it describes */
.kind-row { display: flex; gap: .4rem; align-items: stretch; }
.kind-row .a-input { flex: 1; min-width: 0; }
.kind-pick { display: flex; flex: 0 0 auto; border: 1px solid rgba(60,74,39,.2); border-radius: 10px; overflow: hidden; }
.kind-pick button { padding: 0 .6rem; background: var(--cream-2, rgba(60,74,39,.06)); color: var(--green); font-weight: 700; cursor: pointer; border: none; display: grid; place-items: center; }
.kind-pick button.on { background: var(--green); color: #fff; }
.kind-hint { display: block; color: var(--muted, #8a7f64); font-size: .74rem; margin-top: .3rem; }
</style>
