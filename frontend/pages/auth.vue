<script setup lang="ts">
const api = useApi()
const auth = useAuth()
const toast = useToast()
const mode = ref<'login' | 'register'>('login')
const form = reactive({ name: '', email: '', password: '', telegramCode: '' })
const loading = ref(false)

const finish = async (action: () => Promise<any>) => {
  loading.value = true
  try {
    auth.accept(await action())
    await navigateTo('/dashboard')
  } catch (error: any) {
    toast.add({ title: 'Не удалось войти', description: error?.data?.detail || 'Проверьте данные и повторите.', color: 'error' })
  } finally { loading.value = false }
}

const emailAuth = () => finish(() => api.auth.email(form.email, form.password, mode.value, form.name))
const telegramAuth = () => finish(() => api.auth.telegram(form.telegramCode))
const toggleMode = () => { mode.value = mode.value === 'login' ? 'register' : 'login' }
const googleAuth = async () => {
  const bytes = crypto.getRandomValues(new Uint8Array(64))
  const verifier = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  const challenge = btoa(String.fromCharCode(...new Uint8Array(digest))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const redirectUri = `${location.origin}/auth/google/callback`
  sessionStorage.setItem('yakun_google_verifier', verifier)
  sessionStorage.setItem('yakun_google_redirect_uri', redirectUri)
  const { authorization_url } = await api.auth.googleStart(redirectUri, challenge)
  location.href = authorization_url
}
</script>

<template>
  <main class="page grid min-h-[75vh] place-items-center">
    <UCard class="w-full max-w-md">
      <template #header>
        <h1 class="text-2xl font-bold">{{ mode === 'login' ? 'Вход в Yakun' : 'Создать аккаунт' }}</h1>
        <p class="mt-1 muted">Выберите удобный способ.</p>
      </template>
      <div class="space-y-3">
        <UButton label="Продолжить с Google" icon="i-simple-icons-google" color="neutral" variant="outline" block @click="googleAuth" />
        <USeparator label="или" />
        <UFormField v-if="mode === 'register'" label="Имя"><UInput v-model="form.name" autocomplete="name" class="w-full" /></UFormField>
        <UFormField label="Email"><UInput v-model="form.email" type="email" placeholder="you@example.com" class="w-full" /></UFormField>
        <UFormField label="Пароль"><UInput v-model="form.password" type="password" class="w-full" /></UFormField>
        <UButton :label="mode === 'login' ? 'Войти по email' : 'Зарегистрироваться'" block :loading="loading" @click="emailAuth" />
        <USeparator label="Telegram" />
        <div class="flex gap-2">
          <UInput v-model="form.telegramCode" placeholder="Одноразовый код" class="flex-1" />
          <UButton label="Войти" color="neutral" @click="telegramAuth" />
        </div>
      </div>
      <template #footer>
        <UButton
          :label="mode === 'login' ? 'Нет аккаунта? Зарегистрироваться' : 'Уже есть аккаунт? Войти'"
          variant="link"
          color="neutral"
          block
          @click="toggleMode"
        />
      </template>
    </UCard>
  </main>
</template>
