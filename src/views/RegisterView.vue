<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <div class="auth-top"><LangToggle /></div>
      <RouterLink to="/" class="auth-brand"><span class="g">دكّان</span> كنعان</RouterLink>
      <h1>{{ t('auth.registerTitle') }}</h1>
      <p class="a-muted">{{ t('auth.registerSubtitle') }}</p>
      <form @submit.prevent="submit">
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

const full_name = ref('')
const phone = ref('')
const email = ref('')
const password = ref('')
const confirmPw = ref('')
const error = ref('')
const busy = ref(false)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
// strong password: ≥8 chars, at least one uppercase, one lowercase, one digit
const STRONG_PW_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/

// strip anything that isn't a digit / + - space ( ) as the user types
function onPhone(e) {
  phone.value = e.target.value.replace(/[^\d+\-\s()]/g, '')
}

// Validate a UAE mobile and return it normalized as +9715XXXXXXXX, or null.
// Accepts 05XXXXXXXX, 5XXXXXXXX, 9715XXXXXXXX, +9715XXXXXXXX (with spaces/dashes).
function normalizeUaePhone(raw) {
  let d = (raw || '').replace(/\D/g, '')
  if (d.startsWith('971')) d = d.slice(3)
  else if (d.startsWith('0')) d = d.slice(1)
  return /^5\d{8}$/.test(d) ? '+971' + d : null
}

function validate() {
  if (!EMAIL_RE.test(email.value)) return t('auth.errEmail')
  if (!normalizeUaePhone(phone.value)) return t('auth.errPhoneUAE')
  if (!STRONG_PW_RE.test(password.value)) return t('auth.errPwStrong')
  if (password.value !== confirmPw.value) return t('auth.errPwMatch')
  return ''
}

async function submit() {
  error.value = validate()
  if (error.value) return
  busy.value = true
  try {
    await auth.register({
      full_name: full_name.value,
      phone: normalizeUaePhone(phone.value), // stored as +9715XXXXXXXX
      email: email.value,
      password: password.value,
    })
    router.push(route.query.redirect || '/')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
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
.auth-err { color: var(--red, #9c2b2b); font-size: .85rem; margin-top: .7rem; }
.auth-alt { text-align: center; margin-top: 1.6rem; font-size: .9rem; color: var(--ink); }
.auth-alt a { color: var(--green); font-weight: 700; text-decoration: underline; }
</style>
