<template>
  <AuthShell section="reset" photo="/images/jug.jpg">
    <!-- STEP 1 — which address -->
    <template v-if="step === 'email'">
      <h1>{{ t('auth.forgotTitle') }}</h1>
      <p class="auth-sub">{{ t('auth.forgotSubtitle') }}</p>
      <form @submit.prevent="requestCode">
        <div class="af">
          <label for="fp-email">{{ t('auth.email') }}</label>
          <input id="fp-email" class="a-input" type="email" v-model.trim="email" dir="ltr" required autocomplete="email">
        </div>
        <p v-if="error" class="auth-err">{{ error }}</p>
        <button class="btn btn-green auth-submit" :disabled="busy">{{ busy ? '…' : t('auth.sendCode') }}</button>
      </form>
    </template>

    <!-- STEP 2 — the code, and the new password -->
    <template v-else>
      <h1>{{ t('auth.resetTitle') }}</h1>
      <p class="auth-sub">{{ t('auth.forgotSent') }}</p>
      <form @submit.prevent="submitReset">
        <div class="af af-code">
          <label for="fp-code">{{ t('auth.code') }}</label>
          <p class="auth-sent">{{ sentTo }}</p>
          <input id="fp-code" class="a-input" v-model.trim="code" inputmode="numeric" maxlength="6"
                 dir="ltr" required autocomplete="one-time-code">
        </div>
        <div class="af">
          <label for="fp-pw">{{ t('auth.newPassword') }}</label>
          <PasswordInput id="fp-pw" v-model="password" required autocomplete="new-password" />
        </div>
        <small class="af-hint">{{ t('auth.pwHint') }}</small>
        <div class="af">
          <label for="fp-pw2">{{ t('auth.confirmPassword') }}</label>
          <PasswordInput id="fp-pw2" v-model="confirmPw" required autocomplete="new-password" />
        </div>
        <p v-if="devCode" class="auth-dev">🔧 {{ t('auth.devCodeHint', { code: devCode }) }}</p>
        <p v-if="notice" class="auth-note">{{ notice }}</p>
        <p v-if="error" class="auth-err">{{ error }}</p>
        <button class="btn btn-green auth-submit" :disabled="busy">{{ busy ? '…' : t('auth.saveNewPassword') }}</button>
      </form>
      <div class="auth-minor" style="margin-top:1.2rem">
        <button type="button" class="auth-link" @click="requestCode" :disabled="busy">{{ t('auth.resendCode') }}</button>
        <button type="button" class="auth-link" @click="step = 'email'; error = ''">{{ t('auth.editDetails') }}</button>
      </div>
    </template>

    <div class="auth-sep">{{ t('auth.or') }}</div>
    <p class="auth-alt">
      <RouterLink :to="{ name: 'login', query: $route.query }">{{ t('auth.backToLogin') }}</RouterLink>
    </p>
  </AuthShell>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import AuthShell from '../components/AuthShell.vue'
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
