<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'
import { pendingReferral } from '~/utils/referral'

const api = useApi()
const auth = useAuth()
const toast = useToast()
const { t, tm } = useI18n()
const mode = ref<'login' | 'register'>('login')
const authStep = ref<'form' | 'telegram' | 'email'>('form')
const form = reactive({ name: '', email: '', password: '', telegramCode: '', emailCode: '' })
const loading = ref(false)
const points = computed(() => tm<string[]>('login.points'))
const invited = ref(false)
onMounted(() => { invited.value = Boolean(pendingReferral()) })

const finish = async (action: () => Promise<any>) => {
  loading.value = true
  try {
    await auth.accept(await action())
    await navigateTo('/dashboard')
  } catch (error: any) {
    toast.add({ title: t('login.loginError'), description: apiErrorMessage(error, t('login.loginErrorHint')), color: 'error' })
  } finally { loading.value = false }
}

const requestEmailCode = async () => {
  loading.value = true
  try {
    await api.auth.requestEmailRegister(form.email, form.password, form.name)
    form.emailCode = ''
    authStep.value = 'email'
  } catch (error: any) {
    toast.add({ title: t('login.codeError'), description: apiErrorMessage(error, t('login.loginErrorHint')), color: 'error' })
  } finally { loading.value = false }
}

const emailAuth = () => {
  if (mode.value === 'register') return requestEmailCode()
  return finish(() => api.auth.email(form.email, form.password, 'login'))
}
const confirmEmailCode = () => finish(() => api.auth.confirmEmailRegister(form.email, form.emailCode.trim().toUpperCase()))
const telegramAuth = () => finish(() => api.auth.telegram(form.telegramCode))
const toggleMode = (value?: 'login' | 'register') => {
  mode.value = value || (mode.value === 'login' ? 'register' : 'login')
  authStep.value = 'form'
  form.telegramCode = ''
  form.emailCode = ''
}
const googleAuth = async () => {
  const bytes = crypto.getRandomValues(new Uint8Array(64))
  const verifier = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  const challenge = btoa(String.fromCharCode(...new Uint8Array(digest))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const redirectUri = `${location.origin}/auth/google/callback`
  sessionStorage.setItem('ayakun_google_verifier', verifier)
  sessionStorage.setItem('ayakun_google_redirect_uri', redirectUri)
  sessionStorage.setItem('ayakun_google_purpose', 'login')
  const { authorization_url } = await api.auth.googleStart(redirectUri, challenge)
  location.href = authorization_url
}
</script>

<template>
  <main class="shell auth-page">
    <section class="auth-visual reveal">
      <p class="eyebrow">{{ t('login.eyebrow') }}</p>
      <h1>{{ t('login.title') }}</h1>
      <p class="max-w-xl text-lg leading-8 muted">
        {{ t('login.lead') }}
      </p>
      <div class="auth-points">
        <div v-for="item in points" :key="item" class="auth-point">
          <span class="auth-point-icon"><UIcon name="i-lucide-check" /></span>
          {{ item }}
        </div>
      </div>
    </section>

    <section class="auth-card reveal" style="animation-delay: 100ms">
      <div class="auth-tabs">
        <button class="auth-tab" :class="{ active: mode === 'login' }" @click="toggleMode('login')">{{ t('login.tabLogin') }}</button>
        <button class="auth-tab" :class="{ active: mode === 'register' }" @click="toggleMode('register')">{{ t('login.tabRegister') }}</button>
      </div>

      <h1 class="auth-title">{{ mode === 'login' ? t('login.welcome') : t('login.create') }}</h1>
      <p class="auth-subtitle">
        {{ mode === 'login' ? t('login.loginLead') : t('login.registerLead') }}
      </p>
      <p v-if="invited" class="auth-invite">
        <UIcon name="i-lucide-gift" class="size-4 shrink-0" />
        {{ t('referrals.invitedBanner') }}
      </p>

      <template v-if="authStep === 'form'">
        <div class="auth-providers">
          <button class="auth-provider" type="button" @click="googleAuth">
            <UIcon name="i-simple-icons-google" class="size-5" />
            Google
          </button>
          <a
            href="https://t.me/ayakun_bot?start=logincode"
            target="_blank"
            rel="noopener noreferrer"
            class="auth-provider telegram"
            @click="authStep = 'telegram'"
          >
            <UIcon name="i-simple-icons-telegram" class="size-5" />
            Telegram
            <UIcon name="i-lucide-external-link" class="size-3.5 opacity-60" />
          </a>
        </div>

        <div class="auth-divider">{{ t('login.orEmail') }}</div>
        <div class="space-y-4">
          <UFormField v-if="mode === 'register'" :label="t('login.name')">
            <UInput v-model="form.name" icon="i-lucide-user" autocomplete="name" :placeholder="t('login.namePlaceholder')" size="xl" class="w-full" />
          </UFormField>
          <UFormField label="Email">
            <UInput v-model="form.email" icon="i-lucide-mail" type="email" autocomplete="email" placeholder="name@example.com" size="xl" class="w-full" />
          </UFormField>
          <UFormField :label="t('login.password')">
            <UInput
              v-model="form.password"
              icon="i-lucide-lock"
              type="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              :placeholder="t('login.passwordPlaceholder')"
              size="xl"
              class="w-full"
              @keyup.enter="emailAuth"
            />
          </UFormField>
          <button class="site-button large w-full" type="button" :disabled="loading" @click="emailAuth">
            {{ loading ? t('login.wait') : mode === 'login' ? t('login.enterCabinet') : t('login.getCode') }}
            <UIcon v-if="!loading" name="i-lucide-arrow-right" />
          </button>
        </div>
      </template>

      <template v-else-if="authStep === 'telegram'">
        <div class="telegram-code-box">
          <div class="telegram-code-head">
            <div>
              <p class="font-extrabold text-[#167dac]">{{ t('login.tgCodeTitle') }}</p>
              <p class="muted">{{ t('login.tgCodeHint') }}</p>
            </div>
            <UIcon name="i-simple-icons-telegram" class="mt-1 size-7 shrink-0 text-[#229ed9]" />
          </div>
          <UInput
            v-model="form.telegramCode"
            icon="i-lucide-key-round"
            :placeholder="t('login.tgCodePlaceholder')"
            autocomplete="one-time-code"
            size="xl"
            class="w-full tracking-[0.18em] uppercase"
            @keyup.enter="telegramAuth"
          />
          <button class="site-button telegram large mt-3 w-full" type="button" :disabled="loading || !form.telegramCode.trim()" @click="telegramAuth">
            {{ loading ? t('login.checking') : t('login.enterByCode') }}
          </button>
          <div class="mt-4 flex items-center justify-between">
            <button class="text-button" type="button" @click="authStep = 'form'">{{ t('login.otherWay') }}</button>
            <a href="https://t.me/ayakun_bot?start=logincode" target="_blank" rel="noopener noreferrer" class="text-button">
              {{ t('login.newCode') }}
            </a>
          </div>
        </div>
        <p class="mb-0 mt-4 text-center text-xs leading-5 muted">
          {{ t('login.codeOnce') }}
        </p>
      </template>

      <template v-else>
        <div class="email-code-box">
          <div class="email-code-head">
            <div>
              <p class="font-extrabold text-[var(--violet)]">{{ t('login.emailCodeTitle') }}</p>
              <p class="muted">{{ t('login.emailCodeHint', { email: form.email }) }}</p>
            </div>
            <UIcon name="i-lucide-mail" class="mt-1 size-7 shrink-0 text-[var(--violet)]" />
          </div>
          <UInput
            v-model="form.emailCode"
            icon="i-lucide-key-round"
            :placeholder="t('login.emailCodePlaceholder')"
            autocomplete="one-time-code"
            maxlength="6"
            size="xl"
            class="w-full tracking-[0.18em] uppercase"
            @keyup.enter="confirmEmailCode"
          />
          <button class="site-button large mt-3 w-full" type="button" :disabled="loading || form.emailCode.trim().length !== 6" @click="confirmEmailCode">
            {{ loading ? t('login.checking') : t('login.confirmCreate') }}
          </button>
          <div class="mt-4 flex items-center justify-between">
            <button class="text-button" type="button" @click="authStep = 'form'">{{ t('login.backForm') }}</button>
            <button class="text-button" type="button" :disabled="loading" @click="requestEmailCode">
              {{ t('login.newCode') }}
            </button>
          </div>
        </div>
        <p class="mb-0 mt-4 text-center text-xs leading-5 muted">
          {{ t('login.codeOnce') }}
        </p>
      </template>

      <p v-if="authStep === 'form'" class="mb-0 mt-6 text-center text-xs leading-5 muted">
        {{ t('login.agree') }}
        <NuxtLink to="/terms" class="legal-link">{{ t('login.offer') }}</NuxtLink>
        {{ t('login.and') }}
        <NuxtLink to="/privacy" class="legal-link">{{ t('login.privacy') }}</NuxtLink>.
      </p>
    </section>
  </main>
</template>
