<template>
  <div class="nh">
    <p class="nh-msg">{{ t('help.stuck') }}</p>
    <div class="nh-acts">
      <a class="nh-btn wa" :href="waHref" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm5.6 14.1c-.2.7-1.3 1.3-1.9 1.3-.5 0-1.1.2-3.6-.8-3-1.3-5-4.4-5.1-4.6-.2-.2-1.2-1.6-1.2-3.1 0-1.5.8-2.2 1.1-2.5.3-.3.6-.4.8-.4h.6c.2 0 .4 0 .7.5l.9 2.1c.1.2.1.4 0 .6l-.4.6-.3.3c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.2 1.4 2.5 1.5.3.2.5.1.6 0l1-1.2c.2-.2.4-.2.6-.1l2 1c.3.1.5.2.5.3.1.2.1.7-.1 1.3Z"/></svg>
        {{ t('help.onWhatsapp') }}
      </a>
      <a class="nh-btn" :href="mailHref">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>
        {{ t('help.byEmail') }}
      </a>
    </div>
    <p class="nh-detail" dir="ltr">{{ WHATSAPP_DISPLAY }} · {{ EMAIL }}</p>
  </div>
</template>

<script setup>
// The panel a customer sees when they have hit a dead end the shop caused — a
// payment we cannot get an answer about, an order they cannot open. Those screens
// used to end with an apology and nothing to do next, which leaves somebody holding
// a problem with no way to hand it over.
//
// It also tells the shop. `help_needed` is a struggle action (backend/routers/audit),
// so anyone who saw this appears in the follow-up panel in the manager area with the
// screen they were stuck on — the shop finds out from the log rather than from a
// customer who happens to be persistent enough to write in.
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { track } from '../services/track'
import { EMAIL, WHATSAPP_DISPLAY, whatsappLink, emailLink } from '../utils/contact'

const props = defineProps({
  // which dead end this is, recorded against the customer so a manager knows what
  // they were looking at. Short and stable — it is a key, not a sentence.
  where: { type: String, required: true },
  // what to put in the message box for them, so they arrive with the problem
  // already written down instead of starting from "hello"
  subject: { type: String, default: '' },
})

const { t } = useI18n()

const waHref = computed(() => whatsappLink(props.subject || t('help.stuck')))
const mailHref = computed(() => emailLink(props.subject || t('help.subject')))

// Once per dead end per sitting — the server collapses repeats (see _CLIENT_DEDUPE),
// so a customer reloading a failed payment page is one row, not twenty.
// sent as `reason`: that is the field the follow-up panel reads and renders as
// a pill, so the manager sees which dead end rather than just that there was one
onMounted(() => track('help_needed', { reason: props.where }))
</script>

<style scoped>
.nh {
  margin-top: 1.1rem; padding: .9rem .95rem; border-radius: 14px; text-align: center;
  background: rgba(60, 74, 39, .06); border: 1px solid rgba(60, 74, 39, .16);
}
.nh-msg { margin: 0 0 .7rem; font-size: .88rem; line-height: 1.55; color: var(--green, #3c4a27); }
.nh-acts { display: flex; gap: .5rem; justify-content: center; flex-wrap: wrap; }
.nh-btn {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .5rem .95rem; border-radius: 999px; font-weight: 700; font-size: .84rem;
  background: #fff; color: var(--green, #3c4a27); border: 1px solid rgba(60, 74, 39, .25);
}
.nh-btn svg { width: 17px; height: 17px; }
.nh-btn.wa { background: #25d366; color: #fff; border-color: #25d366; }
.nh-detail { margin: .65rem 0 0; font-size: .74rem; color: var(--muted, #8a7f64); }
</style>
