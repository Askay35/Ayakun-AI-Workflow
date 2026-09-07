<script setup lang="ts">
const route = useRoute()
const api = useApi()
const auth = useAuth()
const error = ref('')

onMounted(async () => {
  try {
    const code = String(route.query.code || '')
    const state = String(route.query.state || '')
    if (!code || !state) throw new Error('Google не вернул code/state')
    const verifier = sessionStorage.getItem('yakun_google_verifier') || ''
    const redirectUri = sessionStorage.getItem('yakun_google_redirect_uri') || `${location.origin}/auth/google/callback`
    if (!verifier) throw new Error('PKCE verifier не найден')
    auth.accept(await api.auth.googleCallback(code, state, verifier, redirectUri))
    sessionStorage.removeItem('yakun_google_verifier')
    sessionStorage.removeItem('yakun_google_redirect_uri')
    await navigateTo('/dashboard')
  } catch (reason: any) {
    error.value = reason?.message || 'Не удалось завершить вход.'
  }
})
</script>

<template>
  <main class="page grid min-h-[70vh] place-items-center text-center">
    <div>
      <UIcon :name="error ? 'i-lucide-circle-alert' : 'i-lucide-loader-circle'" class="size-10" :class="{ 'animate-spin': !error }" />
      <h1 class="mt-3 text-xl font-semibold">{{ error || 'Завершаем вход…' }}</h1>
      <UButton v-if="error" to="/auth" label="Вернуться" class="mt-4" />
    </div>
  </main>
</template>
