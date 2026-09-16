<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'

const route = useRoute()
const api = useApi()
const auth = useAuth()
const error = ref('')
const purpose = ref<'login' | 'gmail' | 'link'>('login')

onMounted(async () => {
  const stored = sessionStorage.getItem('ayakun_google_purpose')
  const storedPurpose = stored === 'gmail' || stored === 'link' ? stored : 'login'
  purpose.value = storedPurpose
  const workflowId = sessionStorage.getItem('ayakun_gmail_workflow') || ''
  const nodeId = sessionStorage.getItem('ayakun_gmail_node') || ''
  try {
    const code = String(route.query.code || '')
    const state = String(route.query.state || '')
    if (!code || !state) throw new Error(storedPurpose === 'gmail' ? 'Не удалось подключить Gmail.' : 'Google не вернул code/state')
    const verifier = sessionStorage.getItem('ayakun_google_verifier') || ''
    const redirectUri = sessionStorage.getItem('ayakun_google_redirect_uri') || `${location.origin}/auth/google/callback`
    if (!verifier) throw new Error(storedPurpose === 'gmail' ? 'Не удалось подключить Gmail.' : 'PKCE verifier не найден')
    const tokens = await api.auth.googleCallback(code, state, verifier, redirectUri)
    await auth.accept(tokens)
    sessionStorage.removeItem('ayakun_google_verifier')
    sessionStorage.removeItem('ayakun_google_redirect_uri')
    sessionStorage.removeItem('ayakun_google_purpose')
    sessionStorage.removeItem('ayakun_gmail_workflow')
    sessionStorage.removeItem('ayakun_gmail_node')
    if (storedPurpose === 'gmail' && workflowId && nodeId && tokens.gmail_account?.id) {
      await navigateTo({
        path: `/workflows/${workflowId}`,
        query: { gmail_node: nodeId, gmail_account: String(tokens.gmail_account.id) }
      })
      return
    }
    if (storedPurpose === 'link') {
      await navigateTo('/profile?tab=integrations')
      return
    }
    await navigateTo(storedPurpose === 'gmail' ? '/workflows' : '/dashboard')
  } catch (reason: any) {
    const fallback = storedPurpose === 'gmail'
      ? 'Не удалось подключить Gmail.'
      : storedPurpose === 'link'
        ? 'Не удалось подключить Google.'
        : 'Не удалось завершить вход.'
    error.value = apiErrorMessage(reason, fallback)
  }
})
</script>

<template>
  <main class="page grid min-h-[70vh] place-items-center text-center">
    <div>
      <UIcon :name="error ? 'i-lucide-circle-alert' : 'i-lucide-loader-circle'" class="size-10" :class="{ 'animate-spin': !error }" />
      <h1 class="mt-3 text-xl font-semibold">{{ error || (purpose === 'gmail' ? 'Подключаем Gmail…' : purpose === 'link' ? 'Подключаем Google…' : 'Завершаем вход…') }}</h1>
      <UButton v-if="error" :to="purpose === 'login' ? '/login' : purpose === 'gmail' ? '/workflows' : '/profile?tab=integrations'" label="Вернуться" class="mt-4" />
    </div>
  </main>
</template>
