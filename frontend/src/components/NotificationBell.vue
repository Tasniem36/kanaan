<template>
  <div class="bell-wrap">
    <button class="bell-btn" @click="toggle" :aria-label="t('inbox.title')" :aria-expanded="open">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
      <span v-if="inbox.unread" class="bell-badge">{{ inbox.unread > 9 ? '9+' : inbox.unread }}</span>
    </button>

    <transition name="v">
      <div v-if="open" class="bell-panel" role="dialog">
        <div class="bell-tabs">
          <button :class="{ on: tab === 'notif' }" @click="tab = 'notif'">{{ t('inbox.notifications') }}</button>
          <button :class="{ on: tab === 'msg' }" @click="goMessages">{{ isManager ? t('inbox.messages') : t('inbox.contactUs') }}</button>
        </div>

        <!-- NOTIFICATIONS -->
        <div v-if="tab === 'notif'" class="bell-body">
          <p v-if="!inbox.notifications.length" class="bell-empty">{{ t('inbox.noNotifs') }}</p>
          <div v-for="n in inbox.notifications" :key="n.id" class="notif" :class="{ unread: !n.read }">
            <b>{{ n.title }}</b>
            <span v-if="n.body" class="notif-body">{{ n.body }}</span>
            <time>{{ fmt(n.created_at) }}</time>
          </div>
        </div>

        <!-- MESSAGES: customer thread -->
        <div v-else-if="!isManager" class="bell-body chat-pane">
          <div ref="chatBox" class="chat">
            <p v-if="!inbox.messages.length" class="bell-empty">{{ t('inbox.startChat') }}</p>
            <div v-for="m in inbox.messages" :key="m.id" class="msg" :class="m.sender">{{ m.body }}</div>
          </div>
          <form class="chat-input" @submit.prevent="send">
            <input v-model="draft" :placeholder="t('inbox.placeholder')" maxlength="2000">
            <button :disabled="!draft.trim() || sending" :aria-label="t('inbox.send')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/></svg>
            </button>
          </form>
        </div>

        <!-- MESSAGES: manager — thread list or an open thread -->
        <div v-else class="bell-body chat-pane">
          <template v-if="!active">
            <p v-if="!inbox.threads.length" class="bell-empty">{{ t('inbox.noThreads') }}</p>
            <button v-for="th in inbox.threads" :key="th.user_id" class="thread" :class="{ unread: Number(th.unread) > 0 }" @click="openThread(th)">
              <span class="thread-top"><b>{{ th.full_name || th.email || '—' }}</b><span v-if="Number(th.unread) > 0" class="thread-badge">{{ th.unread }}</span></span>
              <span class="thread-last">{{ th.last_body }}</span>
            </button>
          </template>
          <template v-else>
            <div class="chat-head">
              <button class="chat-back" @click="active = null" :aria-label="t('inbox.back')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M15 6l-6 6 6 6"/></svg></button>
              <b>{{ active.full_name || active.email }}</b>
            </div>
            <div ref="chatBox" class="chat">
              <div v-for="m in threadMsgs" :key="m.id" class="msg" :class="m.sender">{{ m.body }}</div>
            </div>
            <form class="chat-input" @submit.prevent="sendReply">
              <input v-model="draft" :placeholder="t('inbox.replyPlaceholder')" maxlength="2000">
              <button :disabled="!draft.trim() || sending" :aria-label="t('inbox.send')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/></svg>
              </button>
            </form>
          </template>
        </div>
      </div>
    </transition>
    <div v-if="open" class="bell-backdrop" @click="open = false"></div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useInboxStore } from '../stores/inbox'
import { useAuthStore } from '../stores/auth'

const { t, locale } = useI18n()
const inbox = useInboxStore()
const auth = useAuthStore()
const isManager = auth.isManager

const open = ref(false)
const tab = ref('notif')
const draft = ref('')
const sending = ref(false)
const active = ref(null)       // manager: the open customer thread
const threadMsgs = ref([])
const chatBox = ref(null)

const fmt = (d) => new Date(d).toLocaleString(locale.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

function scrollDown() {
  nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight })
}

async function toggle() {
  open.value = !open.value
  if (!open.value) return
  await inbox.fetchNotifications()
  inbox.markRead()                    // opening the bell clears the badge
  if (tab.value === 'msg') goMessages()
}

async function goMessages() {
  tab.value = 'msg'
  if (isManager) { await inbox.fetchThreads() }
  else { await inbox.fetchMessages(); scrollDown() }
}

async function send() {
  const body = draft.value.trim()
  if (!body || sending.value) return
  sending.value = true
  try { await inbox.sendMessage(body); draft.value = ''; scrollDown() }
  catch { /* surfaced by the API layer */ }
  finally { sending.value = false }
}

async function openThread(th) {
  const { messages } = await inbox.fetchThread(th.user_id)
  threadMsgs.value = messages
  active.value = th
  inbox.fetchThreads()               // refresh unread counts
  scrollDown()
}

async function sendReply() {
  const body = draft.value.trim()
  if (!body || sending.value || !active.value) return
  sending.value = true
  try {
    const m = await inbox.reply(active.value.user_id, body)
    threadMsgs.value.push(m)
    draft.value = ''
    scrollDown()
  } catch { /* ignore */ }
  finally { sending.value = false }
}

onMounted(() => inbox.startPolling())
onBeforeUnmount(() => inbox.stopPolling())
</script>

<style scoped>
.bell-wrap { position: relative; display: inline-flex; }
.bell-btn {
  position: relative; width: 40px; height: 40px; border-radius: 12px;
  display: grid; place-items: center; background: transparent; color: var(--green);
  cursor: pointer; transition: background .15s;
}
.bell-btn:hover { background: var(--cream-2, rgba(60,74,39,.08)); }
.bell-btn svg { width: 22px; height: 22px; }
.bell-badge {
  position: absolute; top: 2px; inset-inline-end: 2px; min-width: 17px; height: 17px;
  padding: 0 4px; border-radius: 9px; background: var(--red, #b23b3b); color: #fff;
  font-size: .68rem; font-weight: 700; display: grid; place-items: center; line-height: 1;
}
.bell-backdrop { position: fixed; inset: 0; z-index: 64; }
.bell-panel {
  position: absolute; z-index: 65; top: calc(100% + .5rem); inset-inline-end: 0;
  width: min(360px, calc(100vw - 2rem)); max-height: 72vh; display: flex; flex-direction: column;
  background: #fff; border: 1px solid rgba(60,74,39,.14); border-radius: 16px;
  box-shadow: 0 20px 44px -16px rgba(0,0,0,.4); overflow: hidden;
}
/* On phones, pin the panel to the viewport (not the tiny bell) so it never gets
   cropped at the screen edge — span the width with small margins, below the header. */
@media (max-width: 560px) {
  .bell-panel {
    position: fixed; top: 62px; inset-inline: .6rem; width: auto;
    max-height: calc(100vh - 74px);
  }
}
.bell-tabs { display: flex; border-bottom: 1px solid rgba(60,74,39,.12); flex: 0 0 auto; }
.bell-tabs button {
  flex: 1; padding: .8rem; background: transparent; border: none; cursor: pointer;
  font-family: inherit; font-size: .9rem; font-weight: 700; color: var(--muted);
  border-bottom: 2px solid transparent; transition: color .15s, border-color .15s;
}
.bell-tabs button.on { color: var(--green); border-bottom-color: var(--green); }
.bell-body { overflow-y: auto; padding: .5rem; }
.bell-empty { color: var(--muted); text-align: center; padding: 1.6rem 1rem; font-size: .9rem; line-height: 1.6; }

.notif { display: grid; gap: .15rem; padding: .6rem .7rem; border-radius: 10px; }
.notif + .notif { border-top: 1px solid rgba(60,74,39,.08); border-radius: 0; }
.notif.unread { background: var(--cream-2, rgba(60,74,39,.07)); border-radius: 10px; }
.notif b { font-size: .9rem; color: var(--green); }
.notif-body { font-size: .84rem; color: var(--ink); }
.notif time { font-size: .72rem; color: var(--muted); }

/* chat pane fills the panel so the input sticks to the bottom */
.chat-pane { display: flex; flex-direction: column; padding: 0; min-height: 320px; }
.chat { flex: 1; overflow-y: auto; padding: .8rem; display: flex; flex-direction: column; gap: .4rem; }
.msg { max-width: 80%; padding: .5rem .75rem; border-radius: 14px; font-size: .9rem; line-height: 1.45; word-break: break-word; }
.msg.customer { align-self: flex-start; background: var(--cream-2, rgba(60,74,39,.1)); color: var(--ink); border-bottom-inline-start-radius: 4px; }
.msg.manager { align-self: flex-end; background: var(--green); color: var(--cream); border-bottom-inline-end-radius: 4px; }
.chat-input { display: flex; gap: .4rem; padding: .5rem; border-top: 1px solid rgba(60,74,39,.12); flex: 0 0 auto; }
.chat-input input {
  flex: 1; border: 1.5px solid rgba(60,74,39,.2); border-radius: 999px; padding: .55rem .9rem;
  font-family: inherit; font-size: .9rem; outline: none; background: #fff; color: var(--ink);
}
.chat-input input:focus { border-color: var(--green); }
.chat-input button {
  flex: 0 0 auto; width: 40px; height: 40px; border-radius: 50%; border: none; cursor: pointer;
  background: var(--green); color: var(--cream); display: grid; place-items: center;
}
.chat-input button:disabled { opacity: .5; cursor: default; }
.chat-input button svg { width: 18px; height: 18px; }
[dir="rtl"] .chat-input button svg { transform: scaleX(-1); }

.thread { display: grid; gap: .2rem; width: 100%; text-align: start; padding: .7rem; border: none; background: transparent; cursor: pointer; border-radius: 10px; }
.thread:hover { background: var(--cream-2, rgba(60,74,39,.06)); }
.thread.unread { background: var(--cream-2, rgba(60,74,39,.1)); }
.thread-top { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.thread-top b { color: var(--green); font-size: .92rem; }
.thread-badge { background: var(--red, #b23b3b); color: #fff; font-size: .7rem; font-weight: 700; min-width: 18px; height: 18px; border-radius: 9px; display: grid; place-items: center; padding: 0 4px; }
.thread-last { font-size: .82rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chat-head { display: flex; align-items: center; gap: .5rem; padding: .6rem .7rem; border-bottom: 1px solid rgba(60,74,39,.12); flex: 0 0 auto; }
.chat-head b { color: var(--green); font-size: .92rem; }
.chat-back { background: var(--cream-2, rgba(60,74,39,.08)); color: var(--green); border: none; width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; cursor: pointer; }
[dir="rtl"] .chat-back svg { transform: scaleX(-1); }
</style>
