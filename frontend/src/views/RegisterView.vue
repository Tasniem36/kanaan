<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <div class="auth-top"><LangToggle /></div>
      <RouterLink to="/" class="auth-brand"><span class="g">دكّان</span> كنعان</RouterLink>

      <!-- STEP 1 — details -->
      <template v-if="step === 'details'">
        <h1>{{ t('auth.registerTitle') }}</h1>
        <p class="a-muted">{{ t('auth.registerSubtitle') }}</p>
        <form @submit.prevent="submitDetails">
          <label class="co-l">{{ t('auth.fullName') }}</label>
          <input class="a-input" v-model.trim="full_name" autocomplete="name">
          <label class="co-l">{{ t('auth.phone') }}</label>
          <input class="a-input" type="tel" inputmode="tel" :value="phone" @input="onPhone" dir="ltr" placeholder="050 123 4567">
          <label class="co-l">{{ t('auth.email') }}</label>
          <input class="a-input" type="email" v-model.trim="email" dir="ltr" required autocomplete="email">
          <label class="co-l">{{ t('auth.password') }}</label>
          <PasswordInput v-model="password" required autocomplete="new-password" />
          <small class="pw-hint">{{ t('auth.pwHint') }}</small>
          <label class="co-l">{{ t('auth.confirmPassword') }}</label>
          <PasswordInput v-model="confirmPw" required autocomplete="new-password" />
          <p v-if="error" class="auth-err">{{ error }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="busy">
            {{ busy ? '…' : t('auth.register') }}
          </button>
        </form>
        <p class="auth-alt">{{ t('auth.haveAccount') }} <RouterLink :to="{ name: 'login', query: $route.query }">{{ t('auth.loginLink') }}</RouterLink></p>
      </template>

      <!-- STEP 2 — verification codes -->
      <template v-else>
        <h1>{{ t('auth.verifyTitle') }}</h1>
        <p class="a-muted">{{ t('auth.verifySubtitle') }}</p>
        <form @submit.prevent="submitCodes">
          <template v-if="emailRequired">
            <label class="co-l">{{ t('auth.emailCode') }} <span v-if="emailOk" class="ok">✓</span></label>
            <p class="sent-to" dir="ltr">{{ sentEmail }}</p>
            <input class="a-input code-input" v-model.trim="emailCode" inputmode="numeric" maxlength="6" dir="ltr" :disabled="emailOk" autocomplete="one-time-code">
          </template>
          <template v-if="phoneRequired">
            <label class="co-l">{{ t('auth.phoneCode') }} <span v-if="phoneOk" class="ok">✓</span></label>
            <p class="sent-to" dir="ltr">{{ sentPhone }}</p>
            <input class="a-input code-input" v-model.trim="phoneCode" inputmode="numeric" maxlength="6" dir="ltr" :disabled="phoneOk">
          </template>
          <p v-if="devCodes" class="dev-hint">🔧 {{ t('auth.devCodesHint', { email: devCodes.email || '—', phone: devCodes.phone || '—' }) }}</p>
          <p v-if="notice" class="auth-note">{{ notice }}</p>
          <p v-if="error" class="auth-err">{{ error }}</p>
          <button class="btn btn-green" style="width:100%;justify-content:center;margin-top:1rem" :disabled="busy">
            {{ busy ? '…' : t('auth.verify') }}
          </button>
        </form>
        <div class="verify-alt">
          <button type="button" class="linkbtn" @click="resend" :disabled="busy">{{ t('auth.resend') }}</button>
          <button type="button" class="linkbtn" @click="backToDetails">{{ t('auth.editDetails') }}</button>
        </div>
      </template>
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
import { normalizeUaePhone } from '../utils/phone'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const step = ref('details')
const full_name = ref('')
const phone = ref('')
const email = ref('')
const password = ref('')
const confirmPw = ref('')
const error = ref('')
const busy = ref(false)

// step 2 state
const verificationId = ref('')
const emailCode = ref('')
const phoneCode = ref('')
const emailOk = ref(false)
const phoneOk = ref(false)
const emailRequired = ref(true)
const phoneRequired = ref(true)
const devCodes = ref(null)
const sentEmail = ref('')
const sentPhone = ref('')
const notice = ref('')

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const STRONG_PW_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/

function onPhone(e) { phone.value = e.target.value.replace(/[^\d+\-\s()]/g, '') }

function validate() {
  if (!EMAIL_RE.test(email.value)) return t('auth.errEmail')
  if (!normalizeUaePhone(phone.value)) return t('auth.errPhoneUAE')
  if (!STRONG_PW_RE.test(password.value)) return t('auth.errPwStrong')
  if (password.value !== confirmPw.value) return t('auth.errPwMatch')
  return ''
}

async function submitDetails() {
  error.value = validate()
  if (error.value) return
  busy.value = true
  try {
    const res = await auth.registerStart({
      full_name: full_name.value,
      phone: normalizeUaePhone(phone.value),
      email: email.value,
      password: password.value,
    })
    // no verification channel configured → account already created + logged in
    if (res.verified) { router.push(route.query.redirect || '/'); return }
    verificationId.value = res.verification_id
    sentEmail.value = res.email
    sentPhone.value = res.phone
    emailRequired.value = res.email_required !== false
    phoneRequired.value = res.phone_required !== false
    devCodes.value = res.dev_codes || null
    emailOk.value = phoneOk.value = false
    emailCode.value = phoneCode.value = error.value = notice.value = ''
    step.value = 'verify'
  } catch (e) { error.value = e.message } finally { busy.value = false }
}

async function submitCodes() {
  error.value = ''
  busy.value = true
  try {
    const res = await auth.registerVerify(verificationId.value, emailCode.value, phoneCode.value)
    if (res.verified) { router.push(route.query.redirect || '/'); return }
    emailOk.value = res.email_ok
    phoneOk.value = res.phone_ok
    error.value = t('auth.errCode')
  } catch (e) {
    error.value = e.message
    if (/expired|start again/i.test(e.message)) step.value = 'details'   // stale → restart
  } finally { busy.value = false }
}

async function resend() {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const res = await auth.registerResend(verificationId.value)
    devCodes.value = res.dev_codes || null
    notice.value = t('auth.resent')
  } catch (e) {
    error.value = e.message
    if (/expired|start again/i.test(e.message)) step.value = 'details'
  } finally { busy.value = false }
}

function backToDetails() { step.value = 'details'; error.value = '' }
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
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin-top: .7rem; }
.auth-note { color: var(--green); font-size: .85rem; margin-top: .7rem; }
.auth-alt { text-align: center; margin-top: 1.6rem; font-size: .9rem; color: var(--ink); }
.auth-alt a { color: var(--green); font-weight: 700; text-decoration: underline; }
/* verification step */
.ok { color: var(--green); font-weight: 800; }
.sent-to { font-size: .82rem; color: var(--muted); margin: -.15rem 0 .4rem; }
.code-input { letter-spacing: .4em; text-align: center; font-size: 1.15rem; font-weight: 700; }
.code-input:disabled { opacity: .6; background: var(--cream-2, rgba(60,74,39,.06)); }
.dev-hint { margin-top: .8rem; font-size: .78rem; color: var(--gold, #b8902f); background: rgba(184,144,47,.1); padding: .4rem .6rem; border-radius: 8px; }
.verify-alt { display: flex; justify-content: space-between; margin-top: 1.3rem; }
.linkbtn { background: none; border: none; color: var(--green); font-family: inherit; font-size: .9rem; font-weight: 700; text-decoration: underline; cursor: pointer; }
.linkbtn:disabled { opacity: .5; cursor: default; }
</style>
