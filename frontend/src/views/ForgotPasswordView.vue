<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <div class="auth-top"><LangToggle /></div>
      <RouterLink to="/" class="auth-brand"><span class="g">دكّان</span> كنعان</RouterLink>

      <!-- STEP 1 — which address -->
      <template v-if="step === 'email'">
        <h1>{{ t('auth.forgotTitle') }}</h1>
        <p class="a-muted">{{ t('auth.forgotSubtitle') }}</p>
        <form @submit.prevent="requestCode">
          <label class="co-l">{{ t('auth.email') }}</label>
          <input class="a-input" type="email" v-model.trim="email" dir="ltr" required autocomplete="email">
          <p v-if="error" class="auth-err">{{ error }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="busy">
            {{ busy ? '…' : t('auth.sendCode') }}
          </button>
        </form>
      </template>

      <!-- STEP 2 — the code, and the new password -->
      <template v-else>
        <h1>{{ t('auth.resetTitle') }}</h1>
        <p class="a-muted">{{ t('auth.forgotSent') }}</p>
        <form @submit.prevent="submitReset">
          <label class="co-l">{{ t('auth.code') }}</label>
          <p class="sent-to" dir="ltr">{{ sentTo }}</p>
          <input class="a-input code-input" v-model.trim="code" inputmode="numeric" maxlength="6"
                 dir="ltr" required autocomplete="one-time-code">
          <label class="co-l">{{ t('auth.newPassword') }}</label>
          <PasswordInput v-model="password" required autocomplete="new-password" />
          <small class="pw-hint">{{ t('auth.pwHint') }}</small>
          <label class="co-l">{{ t('auth.confirmPassword') }}</label>
          <PasswordInput v-model="confirmPw" required autocomplete="new-password" />
          <p v-if="devCode" class="dev-hint">🔧 {{ t('auth.devCodeHint', { code: devCode }) }}</p>
          <p v-if="notice" class="auth-note">{{ notice }}</p>
          <p v-if="error" class="auth-err">{{ error }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="busy">
            {{ busy ? '…' : t('auth.saveNewPassword') }}
          </button>
        </form>
        <div class="verify-alt">
          <button type="button" class="linkbtn" @click="requestCode" :disabled="busy">{{ t('auth.resendCode') }}</button>
          <button type="button" class="linkbtn" @click="step = 'email'; error = ''">{{ t('auth.editDetails') }}</button>
        </div>
      </template>

      <p class="auth-alt">
        <RouterLink :to="{ name: 'login', query: $route.query }">{{ t('auth.backToLogin') }}</RouterLink>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import LangToggle from '../components/LangToggle.vue'
import PasswordInput from '../components/PasswordInput.vue'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const step = ref('email')
const email = ref('')
const code = ref('')
const password = ref('')
const confirmPw = ref('')
const sentTo = ref('')
const devCode = ref('')
const notice = ref('')
const error = ref('')
const busy = ref(false)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const STRONG_PW_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/

// Step 1, and the resend on step 2 — the same call either way.
async function requestCode() {
  if (!EMAIL_RE.test(email.value)) { error.value = t('auth.errEmail'); return }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const res = await auth.forgotPassword(email.value)
    devCode.value = res.dev_code || ''
    // The address is echoed from what we typed, not from the server: the server
    // deliberately doesn't say whether an account exists, and neither do we.
    if (step.value === 'verify') notice.value = t('auth.resent')
    sentTo.value = email.value
    step.value = 'verify'
  } catch (e) { error.value = e.message } finally { busy.value = false }
}

async function submitReset() {
  if (!STRONG_PW_RE.test(password.value)) { error.value = t('auth.errPwStrong'); return }
  if (password.value !== confirmPw.value) { error.value = t('auth.errPwMatch'); return }
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await auth.resetPassword(sentTo.value, code.value, password.value)
    await auth.fetchMe()
    router.push(route.query.redirect || (auth.isManager ? '/manager' : '/'))
  } catch (e) {
    error.value = e.message
    if (/start again/i.test(e.message)) step.value = 'email'   // the code died — begin again
  } finally { busy.value = false }
}
</script>

<style scoped>
.auth-wrap { min-height: 100vh; display: grid; place-items: center; padding: 2rem 1rem; background: var(--cream, #f7f3e9); }
.auth-card { width: 100%; max-width: 420px; background: #fff; border-radius: 20px; padding: 1.6rem 2.2rem 2.4rem; box-shadow: 0 20px 60px rgba(60,74,39,.12); }
.auth-top { display: flex; justify-content: flex-end; margin-bottom: 1rem; }
.auth-brand { display: block; text-align: center; font-family: 'Amiri', serif; font-size: 1.7rem; color: var(--green); margin-bottom: 1.6rem; }
.auth-brand .g { color: var(--gold, #b8902f); }
.auth-card h1 { font-family: 'Amiri', serif; color: var(--green); font-size: 1.6rem; margin-bottom: .25rem; }
.auth-card .a-muted { margin-bottom: .8rem; }
.auth-card form { display: flex; flex-direction: column; }
.auth-card .co-l { display: block; font-size: .85rem; font-weight: 600; color: var(--green); margin: 1rem 0 .4rem; }
.pw-hint { display: block; color: var(--muted, #8a7f64); font-size: .75rem; margin-top: .35rem; }
.sent-to { font-size: .82rem; color: var(--muted); margin: -.15rem 0 .4rem; }
.code-input { letter-spacing: .4em; text-align: center; font-size: 1.15rem; font-weight: 700; }
.dev-hint { margin-top: .8rem; font-size: .78rem; color: var(--gold, #b8902f); background: rgba(184,144,47,.1); padding: .4rem .6rem; border-radius: 8px; }
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin-top: .7rem; }
.auth-note { color: var(--green); font-size: .85rem; margin-top: .7rem; }
.auth-alt { text-align: center; margin-top: 1.6rem; font-size: .9rem; color: var(--ink); }
.auth-alt a { color: var(--green); font-weight: 700; text-decoration: underline; }
.verify-alt { display: flex; justify-content: space-between; margin-top: 1.3rem; }
.linkbtn { background: none; border: none; color: var(--green); font-family: inherit; font-size: .9rem; font-weight: 700; text-decoration: underline; cursor: pointer; }
.linkbtn:disabled { opacity: .5; cursor: default; }
</style>
