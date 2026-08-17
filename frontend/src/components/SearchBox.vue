<template>
  <div class="sb" :class="{ open }">
    <button v-if="!open" class="sb-toggle" :aria-label="t('search.open')" @click="expand">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>
    </button>

    <form v-else class="sb-form" role="search" @submit.prevent="submit">
      <svg class="sb-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>
      <input
        ref="input"
        v-model="term"
        class="sb-input"
        type="search"
        enterkeyhint="search"
        autocomplete="off"
        :placeholder="t('search.placeholder')"
        :aria-label="t('search.placeholder')"
        @keydown.esc="collapse"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter="onEnter"
      >
      <button v-if="term" type="button" class="sb-clear" :aria-label="t('search.clear')" @click="clear">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>
      </button>
      <button type="button" class="sb-close" :aria-label="t('common.close')" @click="collapse">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>
      </button>

      <!-- live suggestions; the last row runs the full search -->
      <ul v-if="showPanel" class="sb-panel" role="listbox">
        <li v-if="loading" class="sb-msg">{{ t('common.loading') }}</li>
        <li v-else-if="!results.length" class="sb-msg">{{ t('search.noResults') }}</li>
        <template v-else>
          <li
            v-for="(p, i) in results"
            :key="p.id"
            role="option"
            :aria-selected="i === cursor"
            :class="['sb-row', { on: i === cursor }]"
            @mousedown.prevent="go(p)"
            @mouseenter="cursor = i"
          >
            <img v-if="thumb(p)" :src="thumb(p)" :alt="pName(p)" loading="lazy" decoding="async">
            <span v-else class="sb-noimg" aria-hidden="true"></span>
            <span class="sb-name">{{ pName(p) }}</span>
            <span class="sb-price">{{ p.price }} <span class="dh" role="img" aria-label="درهم"></span></span>
          </li>
          <li class="sb-all" @mousedown.prevent="submit">{{ t('search.viewAll') }}</li>
        </template>
      </ul>
    </form>

    <!-- click-away closes the expanded field -->
    <div v-if="open" class="sb-backdrop" @click="collapse"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { api } from '../services/api'
import { pName } from '../utils/product'

const { t } = useI18n()
const router = useRouter()

const open = ref(false)
const term = ref('')
const results = ref([])
const loading = ref(false)
const cursor = ref(-1)
const input = ref(null)

const SUGGEST_LIMIT = 6
const showPanel = computed(() => open.value && term.value.trim().length >= 2)

const thumb = (p) => p.thumb_url || p.image_url || ''

// Debounced so typing doesn't fire a request per keystroke, and generation-
// guarded so a slow early response can't overwrite a newer one.
let timer
let gen = 0
function onTerm() {
  clearTimeout(timer)
  cursor.value = -1
  const q = term.value.trim()
  if (q.length < 2) { results.value = []; loading.value = false; return }
  loading.value = true
  timer = setTimeout(async () => {
    const mine = ++gen
    try {
      const qs = new URLSearchParams({ q, limit: SUGGEST_LIMIT, active: '1' })
      const { products } = await api(`/products?${qs}`)
      if (mine !== gen) return
      results.value = products || []
    } catch {
      if (mine === gen) results.value = []
    } finally {
      if (mine === gen) loading.value = false
    }
  }, 250)
}
watch(term, onTerm)

async function expand() {
  open.value = true
  await nextTick()
  input.value?.focus()
}
function collapse() {
  open.value = false
  results.value = []
  cursor.value = -1
  clearTimeout(timer)
}
function clear() {
  term.value = ''
  results.value = []
  input.value?.focus()
}

function move(delta) {
  if (!results.value.length) return
  const n = results.value.length
  cursor.value = (cursor.value + delta + n) % n
}
function go(p) {
  collapse()
  router.push({ name: 'product', params: { id: p.id } })
}
function onEnter() {
  // a highlighted suggestion wins; otherwise run the full search
  if (cursor.value >= 0 && results.value[cursor.value]) go(results.value[cursor.value])
  else submit()
}
function submit() {
  const q = term.value.trim()
  if (!q) return
  collapse()
  router.push({ name: 'search', query: { q } })
}

onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.sb { position: relative; display: inline-flex; }
.sb-toggle {
  width: 38px; height: 38px; display: grid; place-items: center;
  border: none; background: transparent; color: var(--green, #3c4a27);
  border-radius: 50%; cursor: pointer; transition: background 0.2s, color 0.2s;
}
.sb-toggle:hover { background: var(--cream-2, rgba(60, 74, 39, 0.08)); color: var(--gold, #b8902f); }
.sb-toggle svg { width: 20px; height: 20px; }

.sb-form {
  position: relative;
  z-index: 62;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  width: min(340px, 62vw);
  padding: 0.42rem 0.75rem;
  background: var(--paper, #fff);
  border: 1.5px solid rgba(60, 74, 39, 0.2);
  border-radius: 999px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.sb-form:focus-within { border-color: var(--green, #3c4a27); box-shadow: 0 6px 20px -12px rgba(60, 74, 39, 0.6); }
.sb-ic { width: 18px; height: 18px; color: var(--green, #3c4a27); flex: 0 0 auto; }
.sb-input {
  flex: 1; min-width: 0; border: none; outline: none; background: transparent;
  font-family: inherit; font-size: 0.92rem; color: var(--ink, #33301f);
}
.sb-input::-webkit-search-cancel-button { display: none; }
.sb-clear, .sb-close {
  width: 24px; height: 24px; flex: 0 0 auto; display: grid; place-items: center;
  border: none; border-radius: 50%; cursor: pointer;
  background: var(--cream-2, rgba(60, 74, 39, 0.08)); color: var(--green, #3c4a27);
}
.sb-clear svg, .sb-close svg { width: 13px; height: 13px; }
.sb-backdrop { position: fixed; inset: 0; z-index: 61; }

.sb-panel {
  position: absolute;
  z-index: 62;
  top: calc(100% + 0.45rem);
  inset-inline: 0;
  max-height: min(60vh, 380px);
  overflow-y: auto;
  list-style: none;
  margin: 0;
  padding: 0.3rem;
  background: var(--paper, #fff);
  border: 1px solid rgba(60, 74, 39, 0.14);
  border-radius: 14px;
  box-shadow: 0 18px 40px -18px rgba(0, 0, 0, 0.45);
}
.sb-msg { padding: 0.7rem 0.8rem; font-size: 0.86rem; color: var(--muted, #7b7768); text-align: center; }
.sb-row {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.42rem 0.5rem; border-radius: 10px; cursor: pointer;
}
.sb-row.on { background: var(--cream-2, rgba(60, 74, 39, 0.08)); }
.sb-row img, .sb-noimg {
  width: 38px; height: 38px; flex: 0 0 auto; border-radius: 8px;
  object-fit: cover; background: var(--cream-2, rgba(60, 74, 39, 0.08));
}
.sb-name {
  flex: 1; min-width: 0; font-size: 0.88rem; color: var(--ink, #33301f);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sb-price { font-family: 'Amiri', serif; font-size: 1rem; color: var(--terra-deep, #7a3b2e); flex: 0 0 auto; }
.sb-all {
  margin-top: 0.2rem; padding: 0.55rem; border-top: 1px solid rgba(60, 74, 39, 0.1);
  text-align: center; font-size: 0.85rem; font-weight: 700;
  color: var(--green, #3c4a27); cursor: pointer; border-radius: 10px;
}
.sb-all:hover { background: var(--cream-2, rgba(60, 74, 39, 0.08)); }

@media (max-width: 560px) {
  /* the field would never fit beside the brand + cart, so it takes the bar over */
  .sb-form {
    position: fixed;
    inset-inline: 0.7rem;
    top: 0.6rem;
    width: auto;
  }
  .sb-panel { position: fixed; inset-inline: 0.7rem; top: 3.6rem; }
}
</style>
