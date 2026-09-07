<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const auth = useAuth()
const api = useApi()
const toast = useToast()
const tab = ref<'profile' | 'integrations'>('profile')
const name = ref(auth.user.value?.name || '')
const linked = (provider: string) => auth.user.value?.identities?.some(item => item.provider === provider)
const showProfile = () => { tab.value = 'profile' }
const showIntegrations = () => { tab.value = 'integrations' }
const saveProfile = () => { toast.add({ title: 'Профиль сохранён', color: 'success' }) }
const connectGoogle = async () => {
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
  <div class="page max-w-3xl">
    <div class="page-head"><div><h1 class="text-3xl font-bold">Настройки</h1><p class="muted">Профиль и внешние подключения.</p></div></div>
    <div class="mb-5 flex gap-2"><UButton label="Профиль" :variant="tab === 'profile' ? 'solid' : 'ghost'" @click="showProfile" /><UButton label="Интеграции" :variant="tab === 'integrations' ? 'solid' : 'ghost'" @click="showIntegrations" /></div>
    <UCard v-if="tab === 'profile'">
      <div class="space-y-4"><UFormField label="Имя"><UInput v-model="name" class="w-full" /></UFormField><UFormField label="Email"><UInput :model-value="auth.user.value?.email" disabled class="w-full" /></UFormField><UButton label="Сохранить" @click="saveProfile" /></div>
    </UCard>
    <div v-else class="space-y-3">
      <UCard><div class="flex items-center justify-between"><div class="flex items-center gap-3"><UIcon name="i-simple-icons-telegram" class="size-7 text-primary" /><div><h2 class="font-semibold">Telegram</h2><p class="text-sm muted">Доставка результатов цепочек</p></div></div><UBadge v-if="linked('telegram')" label="Подключён" color="success" variant="soft" /><UButton v-else to="/auth" label="Подключить кодом" variant="outline" /></div></UCard>
      <UCard><div class="flex items-center justify-between"><div class="flex items-center gap-3"><UIcon name="i-simple-icons-google" class="size-7" /><div><h2 class="font-semibold">Google</h2><p class="text-sm muted">Дополнительный способ входа</p></div></div><UBadge v-if="linked('google')" label="Подключён" color="success" variant="soft" /><UButton v-else label="Подключить" variant="outline" @click="connectGoogle" /></div></UCard>
    </div>
  </div>
</template>
