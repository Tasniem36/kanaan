<template>
  <section>
    <h1>{{ t('manager.errorsTitle') }}</h1>
    <p class="a-muted" style="margin-bottom:1rem">{{ t('manager.errorsHint') }}</p>
    <Loader v-if="loading" :label="t('common.loading')" />
    <p v-else-if="!errors.length" class="a-muted">{{ t('manager.noErrors') }}</p>
    <div v-else class="table-wrap">
      <table class="a-table">
        <thead><tr><th>{{ t('manager.colWhen') }}</th><th>{{ t('manager.colContact') }}</th><th>{{ t('manager.colPage') }}</th><th>{{ t('manager.colError') }}</th><th></th></tr></thead>
        <tbody>
          <tr v-for="e in errors" :key="e.id">
            <td class="a-muted" style="white-space:nowrap">{{ fmt(e.created_at) }}</td>
            <td>
              <b v-if="e.name" style="color:var(--green)">{{ e.name }}</b>
              <span v-else class="a-muted">{{ t('manager.guestVisitor') }}</span>
              <div class="a-muted contact" dir="ltr">{{ e.email || '' }}<span v-if="e.phone"> · {{ e.phone }}</span></div>
            </td>
            <td class="page-cell"><a v-if="e.page" href="#" class="page-link" dir="ltr" :title="e.page" @click.prevent="goPage(e.page)">{{ e.page }}</a><span v-else class="a-muted">—</span></td>
            <td>
              <span style="color:var(--red);font-size:.86rem">{{ e.message }}</span>
              <div v-if="e.detail" class="err-detail">{{ e.detail }}</div>
            </td>
            <td><button class="a-btn ghost" @click="dismiss(e)">{{ t('manager.dismiss') }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../../services/api'
import Loader from '../../components/Loader.vue'

const { t, locale } = useI18n()
const router = useRouter()
function goPage(p) { try { router.push(p) } catch { /* not an in-app route */ } }
const errors = ref([])
const loading = ref(false)
const fmt = (d) => new Date(d).toLocaleString(locale.value, { dateStyle: 'medium', timeStyle: 'short' })

async function load() {
  loading.value = true
  try { const { errors: rows } = await api('/errors'); errors.value = rows }
  catch { /* e.g. session expired — the auth guard handles the redirect; don't self-report */ }
  finally { loading.value = false }
}
async function dismiss(e) {
  try { await api(`/errors/${e.id}`, { method: 'DELETE' }); errors.value = errors.value.filter((x) => x.id !== e.id) }
  catch { /* ignore */ }
}
onMounted(load)
</script>

<style scoped>
h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.9rem; margin-bottom: .3rem; }
.contact { font-size: .8rem; }
.err-detail { font-size: .74rem; margin-top: .25rem; white-space: pre-wrap; word-break: break-word; max-height: 4.5em; overflow: auto; opacity: .75; }
/* page column: one line, truncated with … (full path on hover), clickable */
.page-cell { max-width: 200px; }
.page-link {
  display: inline-block; max-width: 200px; vertical-align: bottom;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--green); text-decoration: underline; cursor: pointer; font-size: .8rem;
}
.page-link:hover { color: var(--gold); }
.a-btn.ghost { background: var(--cream-2); color: var(--green); }
</style>
