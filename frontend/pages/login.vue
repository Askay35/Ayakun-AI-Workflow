<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'

const api = useApi()
const auth = useAuth()
const toast = useToast()
const mode = ref<'login' | 'register'>('login')
const authStep = ref<'form' | 'telegram' | 'email'>('form')
const form = reactive({ name: '', email: '', password: '', telegramCode: '', emailCode: '' })
const loading = ref(false)

const finish = async (action: () => Promise<any>) => {
  loading.value = true
  try {
    await auth.accept(await action())
    await navigateTo('/dashboard')
  } catch (error: any) {
    toast.add({ title: 'Не удалось войти', description: apiErrorMessage(error, 'Проверьте данные и повторите.'), color: 'error' })
  } finally { loading.value = false }
}

const requestEmailCode = async () => {
  loading.value = true
  try {
    await api.auth.requestEmailRegister(form.email, form.password, form.name)
    form.emailCode = ''
    authStep.value = 'email'
  } catch (error: any) {
    toast.add({ title: 'Не удалось отправить код', description: apiErrorMessage(error, 'Проверьте данные и повторите.'), color: 'error' })
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
  const { authorization_url } = await api.auth.googleStart(redirectUri, challenge)
  location.href = authorization_url
}
</script>

<template>
  <main class="shell auth-page">
    <section class="auth-visual reveal">
      <p class="eyebrow">Один аккаунт — все автоматизации</p>
      <h1>Войдите и продолжайте с того же места</h1>
      <p class="max-w-xl text-lg leading-8 muted">
        Ваши цепочки, расписания и результаты надёжно сохраняются в личном кабинете.
      </p>
      <div class="auth-points">
        <div v-for="item in ['Забудьте про рутину', 'Результаты приходят прямо в мессенджер', 'Расписание доступно на любом тарифе']" :key="item" class="auth-point">
          <span class="auth-point-icon"><UIcon name="i-lucide-check" /></span>
          {{ item }}
        </div>
      </div>
    </section>

    <section class="auth-card reveal" style="animation-delay: 100ms">
      <div class="auth-tabs">
        <button class="auth-tab" :class="{ active: mode === 'login' }" @click="toggleMode('login')">Вход</button>
        <button class="auth-tab" :class="{ active: mode === 'register' }" @click="toggleMode('register')">Регистрация</button>
      </div>

      <h1 class="auth-title">{{ mode === 'login' ? 'Добро пожаловать' : 'Создайте аккаунт' }}</h1>
      <p class="auth-subtitle">
        {{ mode === 'login' ? 'Выберите удобный способ входа.' : 'Начните бесплатно — платёжные данные не нужны.' }}
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

        <div class="auth-divider">или через email</div>
        <div class="space-y-4">
          <UFormField v-if="mode === 'register'" label="Ваше имя">
            <UInput v-model="form.name" icon="i-lucide-user" autocomplete="name" placeholder="Как к вам обращаться" size="xl" class="w-full" />
          </UFormField>
          <UFormField label="Email">
            <UInput v-model="form.email" icon="i-lucide-mail" type="email" autocomplete="email" placeholder="name@example.com" size="xl" class="w-full" />
          </UFormField>
          <UFormField label="Пароль">
            <UInput
              v-model="form.password"
              icon="i-lucide-lock"
              type="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              placeholder="Не менее 8 символов"
              size="xl"
              class="w-full"
              @keyup.enter="emailAuth"
            />
          </UFormField>
          <button class="site-button large w-full" type="button" :disabled="loading" @click="emailAuth">
            {{ loading ? 'Подождите…' : mode === 'login' ? 'Войти в кабинет' : 'Получить код' }}
            <UIcon v-if="!loading" name="i-lucide-arrow-right" />
          </button>
        </div>
      </template>

      <template v-else-if="authStep === 'telegram'">
        <div class="telegram-code-box">
          <div class="telegram-code-head">
            <div>
              <p class="font-extrabold text-[#167dac]">Код отправлен в Telegram</p>
              <p class="muted">Откройте бота, нажмите «Старт» и скопируйте полученный код сюда.</p>
            </div>
            <UIcon name="i-simple-icons-telegram" class="mt-1 size-7 shrink-0 text-[#229ed9]" />
          </div>
          <UInput
            v-model="form.telegramCode"
            icon="i-lucide-key-round"
            placeholder="Код из Telegram"
            autocomplete="one-time-code"
            size="xl"
            class="w-full tracking-[0.18em] uppercase"
            @keyup.enter="telegramAuth"
          />
          <button class="site-button telegram large mt-3 w-full" type="button" :disabled="loading || !form.telegramCode.trim()" @click="telegramAuth">
            {{ loading ? 'Проверяем код…' : 'Войти по коду' }}
          </button>
          <div class="mt-4 flex items-center justify-between">
            <button class="text-button" type="button" @click="authStep = 'form'">Другой способ входа</button>
            <a href="https://t.me/ayakun_bot?start=logincode" target="_blank" rel="noopener noreferrer" class="text-button">
              Получить новый код
            </a>
          </div>
        </div>
        <p class="mb-0 mt-4 text-center text-xs leading-5 muted">
          Код одноразовый и действует ограниченное время.
        </p>
      </template>

      <template v-else>
        <div class="email-code-box">
          <div class="email-code-head">
            <div>
              <p class="font-extrabold text-[var(--violet)]">Код отправлен на почту</p>
              <p class="muted">Проверьте {{ form.email }} и введите код подтверждения.</p>
            </div>
            <UIcon name="i-lucide-mail" class="mt-1 size-7 shrink-0 text-[var(--violet)]" />
          </div>
          <UInput
            v-model="form.emailCode"
            icon="i-lucide-key-round"
            placeholder="Код из письма"
            autocomplete="one-time-code"
            maxlength="6"
            size="xl"
            class="w-full tracking-[0.18em] uppercase"
            @keyup.enter="confirmEmailCode"
          />
          <button class="site-button large mt-3 w-full" type="button" :disabled="loading || form.emailCode.trim().length !== 6" @click="confirmEmailCode">
            {{ loading ? 'Проверяем код…' : 'Подтвердить и создать аккаунт' }}
          </button>
          <div class="mt-4 flex items-center justify-between">
            <button class="text-button" type="button" @click="authStep = 'form'">Назад к форме</button>
            <button class="text-button" type="button" :disabled="loading" @click="requestEmailCode">
              Получить новый код
            </button>
          </div>
        </div>
        <p class="mb-0 mt-4 text-center text-xs leading-5 muted">
          Код одноразовый и действует ограниченное время.
        </p>
      </template>

      <p v-if="authStep === 'form'" class="mb-0 mt-6 text-center text-xs leading-5 muted">
        Продолжая, вы соглашаетесь с
        <NuxtLink to="/terms" class="legal-link">публичной офертой</NuxtLink>.
      </p>
    </section>
  </main>
</template>
