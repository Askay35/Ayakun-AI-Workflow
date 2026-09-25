<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'

definePageMeta({ layout: 'app', middleware: 'auth' })
const auth = useAuth()
const api = useApi()
const toast = useToast()
const { t } = useI18n()
const route = useRoute()
const tab = ref<'profile' | 'integrations'>(route.query.tab === 'integrations' ? 'integrations' : 'profile')
const name = ref(auth.user.value?.name || '')
const email = ref(auth.user.value?.email || '')
const emailCode = ref('')
const emailStep = ref(false)
const saving = ref(false)
const linking = ref(false)
const telegramStep = ref(false)
const telegramCode = ref('')
const linked = (provider: string) => auth.user.value?.identities?.some(item => item.provider === provider)
const currentEmail = computed(() => (auth.user.value?.email || '').trim().toLowerCase())
const emailLocked = computed(() => Boolean(currentEmail.value))
const pendingEmail = computed(() => email.value.trim().toLowerCase())
const emailChanged = computed(() => pendingEmail.value !== currentEmail.value)

const showProfile = () => { tab.value = 'profile' }
const showIntegrations = () => { tab.value = 'integrations' }
const openTelegramStep = () => { telegramStep.value = true }
const closeTelegramStep = () => { telegramStep.value = false }
const cancelEmailStep = () => {
  emailStep.value = false
  emailCode.value = ''
}

const saveProfile = async () => {
  saving.value = true
  try {
    const payload: { name?: string; email?: string } = {}
    if (name.value.trim() && name.value.trim() !== (auth.user.value?.name || '')) {
      payload.name = name.value.trim()
    }
    if (!emailLocked.value && emailChanged.value) {
      if (!pendingEmail.value) {
        toast.add({ title: t('profile.emailRequired'), color: 'error' })
        return
      }
      payload.email = pendingEmail.value
    }
    if (!payload.name && !payload.email) {
      toast.add({ title: t('profile.noChanges'), color: 'neutral' })
      return
    }
    const user = await api.auth.updateProfile(payload)
    auth.user.value = user
    name.value = user.name || name.value
    if (payload.email) {
      emailStep.value = true
      emailCode.value = ''
      toast.add({ title: t('profile.codeSent'), description: t('profile.codeSentHint'), color: 'success' })
    } else {
      toast.add({ title: t('profile.saved'), color: 'success' })
    }
  } catch (error: any) {
    toast.add({ title: t('profile.saveError'), description: apiErrorMessage(error, t('profile.saveErrorHint')), color: 'error' })
  } finally {
    saving.value = false
  }
}

const confirmEmail = async () => {
  saving.value = true
  try {
    auth.user.value = await api.auth.confirmEmailLink(pendingEmail.value, emailCode.value.trim().toUpperCase())
    email.value = auth.user.value?.email || email.value
    emailStep.value = false
    emailCode.value = ''
    toast.add({ title: t('profile.emailOk'), color: 'success' })
  } catch (error: any) {
    toast.add({ title: t('profile.emailFail'), description: apiErrorMessage(error, t('profile.emailFailHint')), color: 'error' })
  } finally {
    saving.value = false
  }
}

const startGoogle = async (purpose: 'login' | 'link') => {
  linking.value = true
  try {
    const bytes = crypto.getRandomValues(new Uint8Array(64))
    const verifier = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
    const challenge = btoa(String.fromCharCode(...new Uint8Array(digest))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    const redirectUri = `${location.origin}/auth/google/callback`
    sessionStorage.setItem('ayakun_google_verifier', verifier)
    sessionStorage.setItem('ayakun_google_redirect_uri', redirectUri)
    sessionStorage.setItem('ayakun_google_purpose', purpose)
    const { authorization_url } = await api.auth.googleStart(redirectUri, challenge, purpose)
    location.href = authorization_url
  } catch (error: any) {
    toast.add({ title: t('profile.googleFail'), description: apiErrorMessage(error, t('profile.tryAgain')), color: 'error' })
    linking.value = false
  }
}

const connectGoogle = () => startGoogle('link')
const linkTelegram = async () => {
  linking.value = true
  try {
    auth.user.value = await api.auth.telegramLink(telegramCode.value.trim().toUpperCase())
    telegramCode.value = ''
    telegramStep.value = false
    toast.add({ title: t('profile.tgOk'), color: 'success' })
  } catch (error: any) {
    toast.add({ title: t('profile.tgFail'), description: apiErrorMessage(error, t('profile.saveErrorHint')), color: 'error' })
  } finally {
    linking.value = false
  }
}
</script>

<template>
  <div class="page max-w-3xl">
    <div class="page-head"><div><p class="eyebrow">{{ t('profile.eyebrow') }}</p><h1 class="page-title">{{ t('profile.title') }}</h1><p class="muted">{{ t('profile.lead') }}</p></div></div>
    <div class="mb-6 inline-flex gap-1 rounded-xl border border-[var(--line)] bg-white p-1 shadow-[var(--shadow-sm)]"><UButton :label="t('profile.tabProfile')" :variant="tab === 'profile' ? 'soft' : 'ghost'" @click="showProfile" /><UButton :label="t('profile.tabIntegrations')" :variant="tab === 'integrations' ? 'soft' : 'ghost'" @click="showIntegrations" /></div>
    <div v-if="tab === 'profile'" class="panel p-6">
      <div class="mb-6 flex items-center gap-4"><span class="grid size-14 place-items-center rounded-2xl text-xl font-extrabold text-white shadow-[0_8px_18px_rgba(109,74,255,.25)]" style="background: var(--grad)">{{ (name || email || 'A').slice(0, 1).toUpperCase() }}</span><div><h2 class="mb-1 text-xl font-extrabold tracking-tight">{{ t('profile.personal') }}</h2><p class="mb-0 text-sm muted">{{ t('profile.personalHint') }}</p></div></div>
      <div class="space-y-4">
        <UFormField :label="t('profile.name')"><UInput v-model="name" size="lg" class="w-full" /></UFormField>
        <UFormField label="Email">
          <UInput
            v-model="email"
            type="email"
            autocomplete="email"
            size="lg"
            class="w-full"
            :disabled="emailLocked"
            placeholder="name@example.com"
          />
        </UFormField>
        <p v-if="!emailLocked" class="mb-0 text-sm muted">{{ t('profile.emailHint') }}</p>
        <div v-if="emailStep" class="space-y-3 rounded-2xl border border-[rgba(109,74,255,.2)] bg-[var(--violet-soft)] p-4">
          <p class="mb-0 text-sm muted">{{ t('profile.codeSentTo', { email: pendingEmail }) }}</p>
          <UInput
            v-model="emailCode"
            icon="i-lucide-key-round"
            :placeholder="t('login.emailCodePlaceholder')"
            autocomplete="one-time-code"
            maxlength="6"
            size="lg"
            class="w-full tracking-[0.18em] uppercase"
            @keyup.enter="confirmEmail"
          />
          <div class="flex gap-2">
            <UButton :label="t('profile.confirmEmail')" :loading="saving" :disabled="emailCode.trim().length !== 6" @click="confirmEmail" />
            <UButton :label="t('common.cancel')" variant="ghost" color="neutral" @click="cancelEmailStep" />
          </div>
        </div>
        <UButton v-else :label="t('profile.saveChanges')" size="lg" :loading="saving" @click="saveProfile" />
      </div>
    </div>
    <div v-else class="space-y-3">
      <div class="panel p-5">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <span class="grid size-12 place-items-center rounded-2xl bg-[rgba(34,158,217,.1)] text-[#229ed9]"><UIcon name="i-simple-icons-telegram" class="size-6" /></span>
            <div>
              <h2 class="mb-1 font-extrabold">Telegram</h2>
              <p class="mb-0 text-sm muted">{{ t('profile.tgHint') }}</p>
            </div>
          </div>
          <UBadge v-if="linked('telegram')" :label="t('profile.connected')" color="success" variant="soft" />
          <UButton v-else :label="t('profile.connect')" variant="outline" @click="openTelegramStep" />
        </div>
        <div v-if="telegramStep && !linked('telegram')" class="mt-4 space-y-3 border-t border-[var(--line)] pt-4">
          <p class="mb-0 text-sm muted">{{ t('profile.tgLinkHint') }}</p>
          <a href="https://t.me/ayakun_bot?start=link" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2 text-sm font-bold text-[#229ed9]">
            {{ t('profile.openBot') }}
            <UIcon name="i-lucide-external-link" class="size-3.5" />
          </a>
          <UInput
            v-model="telegramCode"
            icon="i-lucide-key-round"
            :placeholder="t('login.tgCodePlaceholder')"
            autocomplete="one-time-code"
            size="lg"
            class="w-full tracking-[0.18em] uppercase"
            @keyup.enter="linkTelegram"
          />
          <div class="flex gap-2">
            <UButton :label="t('profile.bind')" :loading="linking" :disabled="!telegramCode.trim()" @click="linkTelegram" />
            <UButton :label="t('common.cancel')" variant="ghost" color="neutral" @click="closeTelegramStep" />
          </div>
        </div>
      </div>
      <div class="panel p-5"><div class="flex items-center justify-between gap-4"><div class="flex items-center gap-4"><span class="grid size-12 place-items-center rounded-2xl bg-[var(--soft)]"><UIcon name="i-simple-icons-google" class="size-6" /></span><div><h2 class="mb-1 font-extrabold">Google</h2><p class="mb-0 text-sm muted">{{ t('profile.googleHint') }}</p></div></div><UBadge v-if="linked('google')" :label="t('profile.connected')" color="success" variant="soft" /><UButton v-else :label="t('profile.connect')" variant="outline" :loading="linking" @click="connectGoogle" /></div></div>
    </div>
  </div>
</template>
