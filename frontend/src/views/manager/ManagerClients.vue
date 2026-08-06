<template>
  <section>
    <h1>{{ t('manager.clientsTitle') }}</h1>
    <Loader v-if="loading" :label="t('common.loading')" />
    <p v-else-if="!clients.length" class="a-muted">{{ t('manager.noClients') }}</p>
    <div v-else class="table-wrap">
      <table class="a-table">
        <thead><tr><th>{{ t('manager.colClient') }}</th><th>{{ t('manager.colRole') }}</th><th>{{ t('manager.colPhone') }}</th><th>{{ t('manager.colOrders') }}</th><th>{{ t('manager.colSpent') }}</th><th>{{ t('manager.colLast') }}</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in visibleClients" :key="c.id">
            <td><b style="color:var(--green)">{{ c.full_name || '—' }}</b><br><span class="a-muted" dir="ltr">{{ c.email }}</span></td>
            <td><span class="a-pill" :class="c.role === 'manager' ? 'pill-warn' : 'pill-ok'">{{ c.role === 'manager' ? t('manager.roleAdmin') : t('manager.roleCustomer') }}</span></td>
            <td dir="ltr">{{ c.phone || '—' }}</td>
            <td>{{ c.orders_count }}</td>
            <td>{{ c.total_spent }} <span class='dh' role='img' aria-label='درهم'></span></td>
            <td class="a-muted">{{ c.last_order_at ? fmtDate(c.last_order_at) : t('manager.none') }}</td>
            <td>
              <div v-if="c.role !== 'manager'" class="cl-actions">
                <button class="cl-icon msg" @click="openMessage(c)" :title="t('manager.msgSend')" :aria-label="t('manager.msgSend')">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></svg>
                </button>
                <button class="cl-icon del" @click="deleteClient(c)" :title="t('manager.delUserTitle')" :aria-label="t('manager.delUserTitle')">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="hasMore"><td colspan="7"><div ref="sentinel" class="load-more"><span class="ld-spin"></span></div></td></tr>
        </tbody>
      </table>
    </div>

    <!-- compose a message to a customer -->
    <Dialog :open="!!composeFor" :title="t('manager.msgTitle', { name: composeFor && (composeFor.full_name || composeFor.email) })" max-width="440px" @close="composeFor = null">
      <textarea class="a-input" rows="4" v-model.trim="composeText" :placeholder="t('manager.msgPlaceholder')"></textarea>
      <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="!composeText || composeBusy" @click="sendMessage">
        {{ composeBusy ? '…' : t('manager.msgSend') }}
      </button>
    </Dialog>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useInboxStore } from '../../stores/inbox'
import { useToastStore } from '../../stores/toast'
import { useConfirmStore } from '../../stores/confirm'
import Loader from '../../components/Loader.vue'
import Dialog from '../../components/Dialog.vue'

const { t, locale } = useI18n()
const inbox = useInboxStore()
const toast = useToastStore()
const confirm = useConfirmStore()
const clients = ref([])
const loading = ref(false)
const { visible: visibleClients, sentinel, hasMore } = useInfiniteScroll(() => clients.value, 10)

const fmtDate = (d) => new Date(d).toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })

// message a customer
const composeFor = ref(null)
const composeText = ref('')
const composeBusy = ref(false)
function openMessage(c) { composeFor.value = c; composeText.value = '' }
async function sendMessage() {
  if (!composeText.value || !composeFor.value) return
  composeBusy.value = true
  try {
    await inbox.reply(composeFor.value.id, composeText.value)
    toast.show(t('manager.msgSent'))
    composeFor.value = null
    composeText.value = ''
  } catch (e) { toast.show(e.message) } finally { composeBusy.value = false }
}

// delete a customer (admin only, guarded server-side)
async function deleteClient(c) {
  const ok = await confirm.ask({
    title: t('manager.delUserTitle'),
    message: t('manager.delUserMsg', { name: c.full_name || c.email }),
    confirmText: t('manager.delUserYes'),
    danger: true,
  })
  if (!ok) return
  try {
    await api(`/users/${c.id}`, { method: 'DELETE' })
    clients.value = clients.value.filter((x) => x.id !== c.id)
    toast.show(t('manager.userDeleted'))
  } catch (e) { toast.show(e.message) }
}

onMounted(async () => {
  loading.value = true
  try { const { clients: c } = await api('/users/clients'); clients.value = c }
  finally { loading.value = false }
})
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: 1rem; }
.cl-actions { display: flex; gap: .4rem; }
.cl-icon {
  width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center;
  border: 1.5px solid rgba(60,74,39,.2); background: transparent; cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
}
.cl-icon svg { width: 16px; height: 16px; }
.cl-icon.msg { color: var(--green); }
.cl-icon.msg:hover { background: var(--green); color: #fff; border-color: var(--green); }
.cl-icon.del { color: var(--red, #b23b3b); border-color: rgba(178,59,59,.3); }
.cl-icon.del:hover { background: var(--red, #b23b3b); color: #fff; }
</style>
