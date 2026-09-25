<script setup lang="ts">
import { takeAfterLogin } from '~/utils/after-login'
import { apiErrorMessage } from '~/composables/useApi'

const route = useRoute()
const api = useApi()
const auth = useAuth()
const { t } = useI18n()
const error = ref('')
const purpose = ref<'login' | 'link'>('login')

onMounted(async () => {
  const stored = sessionStorage.getItem('ayakun_google_purpose')
  const storedPurpose = stored === 'link' ? 'link' : 'login'
  purpose.value = storedPurpose
  try {
    const code = String(route.query.code || '')
    const state = String(route.query.state || '')
    if (!code || !state) throw new Error(t('google.noCode'))
    const verifier = sessionStorage.getItem('ayakun_google_verifier') || ''
    const redirectUri = sessionStorage.getItem('ayakun_google_redirect_uri') || `${location.origin}/auth/google/callback`
    if (!verifier) throw new Error(t('google.noVerifier'))
    const tokens = await api.auth.googleCallback(code, state, verifier, redirectUri)
    await auth.accept(tokens)
    sessionStorage.removeItem('ayakun_google_verifier')
    sessionStorage.removeItem('ayakun_google_redirect_uri')
    sessionStorage.removeItem('ayakun_google_purpose')
    sessionStorage.removeItem('ayakun_gmail_workflow')
    sessionStorage.removeItem('ayakun_gmail_node')
    if (storedPurpose === 'link') {
      await navigateTo('/profile?tab=integrations')
      return
    }
    await navigateTo(takeAfterLogin())
  } catch (reason: any) {
    const fallback = storedPurpose === 'link'
      ? t('google.linkFail')
      : t('google.loginFail')
    error.value = apiErrorMessage(reason, fallback)
  }
})
</script>

<template>
  <main class="page grid min-h-[70vh] place-items-center text-center">
    <div>
      <UIcon :name="error ? 'i-lucide-circle-alert' : 'i-lucide-loader-circle'" class="size-10" :class="{ 'animate-spin': !error }" />
      <h1 class="mt-3 text-xl font-semibold">{{ error || (purpose === 'link' ? t('google.linking') : t('google.finishing')) }}</h1>
      <UButton v-if="error" :to="purpose === 'login' ? '/login' : '/profile?tab=integrations'" :label="t('common.back')" class="mt-4" />
    </div>
  </main>
</template>
