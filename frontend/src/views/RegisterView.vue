<template>
  <AuthShell photo="/images/tatreez.jpg">
    <!-- STEP 1 — details -->
    <template v-if="step === 'details'">
      <h1>{{ t('auth.registerTitle') }}</h1>
      <p class="auth-sub">{{ t('auth.registerSubtitle') }}</p>
      <form @submit.prevent="submitDetails">
        <div class="af">
          <label for="rg-name">{{ t('auth.fullName') }}</label>
          <input id="rg-name" class="a-input" v-model.trim="full_name" autocomplete="name">
        </div>
        <div class="af">
          <label for="rg-phone">{{ t('auth.phone') }}</label>
          <input id="rg-phone" class="a-input" type="tel" inputmode="tel" :value="phone" @input="onPhone" dir="ltr" placeholder="050 123 4567">
        </div>
        <div class="af">
          <label for="rg-email">{{ t('auth.email') }}</label>
          <input id="rg-email" class="a-input" type="email" v-model.trim="email" dir="ltr" required autocomplete="email">
        </div>
        <div class="af">
          <label for="rg-pw">{{ t('auth.password') }}</label>
          <PasswordInput id="rg-pw" v-model="password" required autocomplete="new-password" />
        </div>
        <small class="af-hint">{{ t('auth.pwHint') }}</small>
        <div class="af">
          <label for="rg-pw2">{{ t('auth.confirmPassword') }}</label>
          <PasswordInput id="rg-pw2" v-model="confirmPw" required autocomplete="new-password" />
        </div>
        <p v-if="error" class="auth-err">{{ error }}</p>
        <button class="btn btn-green auth-submit" :disabled="busy">{{ busy ? '…' : t('auth.register') }}</button>
      </form>

      <div class="auth-sep">{{ t('auth.or') }}</div>
      <p class="auth-alt">
        {{ t('auth.haveAccount') }}
        <RouterLink :to="{ name: 'login', query: $route.query }">{{ t('auth.loginLink') }}</RouterLink>
      </p>
    </template>

    <!-- STEP 2 — verification codes -->
    <template v-else>
      <h1>{{ t('auth.verifyTitle') }}</h1>
      <p class="auth-sub">{{ t('auth.verifySubtitle') }}</p>
      <form @submit.prevent="submitCodes">
        <div v-if="emailRequired" class="af af-code" :class="{ done: emailOk }">
          <label for="vf-email">{{ t('auth.emailCode') }} <span v-if="emailOk" class="ok">✓</span></label>
          <p class="auth-sent">{{ sentEmail }}</p>
          <input id="vf-email" class="a-input" v-model.trim="emailCode" inputmode="numeric" maxlength="6" dir="ltr" :disabled="emailOk" autocomplete="one-time-code">
        </div>
        <div v-if="phoneRequired" class="af af-code" :class="{ done: phoneOk }">
          <label for="vf-phone">{{ t('auth.phoneCode') }} <span v-if="phoneOk" class="ok">✓</span></label>
          <p class="auth-sent">{{ sentPhone }}</p>
          <input id="vf-phone" class="a-input" v-model.trim="phoneCode" inputmode="numeric" maxlength="6" dir="ltr" :disabled="phoneOk">
        </div>
        <p v-if="devCodes" class="auth-dev">🔧 {{ t('auth.devCodesHint', { email: devCodes.email || '—', phone: devCodes.phone || '—' }) }}</p>
        <p v-if="notice" class="auth-note">{{ notice }}</p>
        <p v-if="error" class="auth-err">{{ error }}</p>
        <button class="btn btn-green auth-submit" :disabled="busy">{{ busy ? '…' : t('auth.verify') }}</button>
      </form>
      <div class="auth-minor" style="margin-top:1.2rem">
        <button type="button" class="auth-link" @click="resend" :disabled="busy">{{ t('auth.resend') }}</button>
        <button type="button" class="auth-link" @click="backToDetails">{{ t('auth.editDetails') }}</button>
      </div>
    </template>
  </AuthShell>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import AuthShell from '../components/AuthShell.vue'
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
.ok { color: var(--green); font-weight: 800; }
</style>
