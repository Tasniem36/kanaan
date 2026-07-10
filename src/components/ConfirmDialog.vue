<template>
  <transition name="v">
    <div v-if="confirm.open" class="cd-overlay" @click.self="cancel">
      <div class="cd" role="dialog" aria-modal="true">
        <div class="cd-icon" :class="{ danger: o.danger }">
          <svg v-if="o.danger" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 8v4M12 16h.01"/></svg>
        </div>
        <h3>{{ o.title }}</h3>
        <p v-if="o.message">{{ o.message }}</p>
        <div class="cd-actions">
          <button v-if="!o.alert" class="cd-btn cd-cancel" @click="cancel">{{ o.cancelText || t('confirm.cancel') }}</button>
          <button class="cd-btn" :class="o.danger ? 'cd-danger' : 'cd-ok'" @click="confirm.respond(true)" autofocus>{{ o.confirmText || t('confirm.ok') }}</button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirmStore } from '../stores/confirm'

const { t } = useI18n()
const confirm = useConfirmStore()
const o = computed(() => confirm.options)

function cancel() {
  confirm.respond(false)
}
</script>

<style scoped>
.cd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(30, 34, 20, 0.5);
  backdrop-filter: blur(3px);
  display: grid;
  place-items: center;
  z-index: 1000;
  padding: 1rem;
}
.cd {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 20px;
  padding: 1.8rem 1.6rem 1.4rem;
  text-align: center;
  box-shadow: 0 24px 70px rgba(30, 34, 20, 0.28);
}
.cd-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  margin: 0 auto 0.9rem;
  background: rgba(60, 74, 39, 0.1);
  color: var(--green, #3c4a27);
}
.cd-icon svg { width: 28px; height: 28px; }
.cd-icon.danger { background: rgba(156, 43, 43, 0.12); color: var(--red, #9c2b2b); }
.cd h3 { font-family: 'Amiri', serif; font-size: 1.4rem; color: var(--ink, #2b2b22); margin-bottom: 0.3rem; }
.cd p { color: #6b6f5e; font-size: 0.95rem; line-height: 1.6; }
.cd-actions { display: flex; gap: 0.6rem; margin-top: 1.4rem; }
.cd-btn { flex: 1; padding: 0.7rem 1rem; border-radius: 12px; font-weight: 700; font-size: 0.95rem; cursor: pointer; transition: filter 0.15s; }
.cd-btn:hover { filter: brightness(0.95); }
.cd-cancel { background: rgba(60, 74, 39, 0.08); color: var(--ink, #2b2b22); }
.cd-ok { background: var(--green, #3c4a27); color: #fff; }
.cd-danger { background: var(--red, #9c2b2b); color: #fff; }
</style>
