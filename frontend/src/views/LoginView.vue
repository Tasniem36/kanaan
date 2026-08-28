<template>
  <AuthShell section="login" photo="/images/olives.jpg">
    <h1>{{ t('auth.loginTitle') }}</h1>
    <p class="auth-sub">{{ t('auth.loginSubtitle') }}</p>

    <form @submit.prevent="submit">
      <div class="af">
        <label for="login-email">{{ t('auth.email') }}</label>
        <input id="login-email" class="a-input" type="email" v-model.trim="email" dir="ltr" required autocomplete="email">
      </div>

      <div class="af">
        <label for="login-pw">{{ t('auth.password') }}</label>
        <PasswordInput id="login-pw" v-model="password" required autocomplete="current-password" />
      </div>

      <div class="auth-minor">
        <RouterLink class="auth-link" :to="{ name: 'forgot-password', query: $route.query }">
          {{ t('auth.forgotPw') }}
        </RouterLink>
      </div>

      <p v-if="error" class="auth-err">{{ error }}</p>

      <button class="btn btn-green auth-submit" :disabled="busy">
        {{ busy ? '…' : t('auth.login') }}
      </button>
    </form>

    <div class="auth-sep">{{ t('auth.or') }}</div>
    <p class="auth-alt">
      {{ t('auth.noAccount') }}
      <RouterLink :to="{ name: 'register', query: $route.query }">{{ t('auth.createAccount') }}</RouterLink>
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

const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.login(email.value, password.value)
    await auth.fetchMe()
    const dest = route.query.redirect || (auth.isManager ? '/manager' : '/')
    router.push(dest)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
