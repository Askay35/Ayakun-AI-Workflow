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
    <div class="page-head"><div><p class="eyebrow">Аккаунт</p><h1 class="page-title">Настройки</h1><p class="muted">Личные данные и сервисы для доставки результатов.</p></div></div>
    <div class="mb-6 inline-flex rounded-xl bg-white p-1 shadow-sm"><UButton label="Профиль" :variant="tab === 'profile' ? 'soft' : 'ghost'" @click="showProfile" /><UButton label="Интеграции" :variant="tab === 'integrations' ? 'soft' : 'ghost'" @click="showIntegrations" /></div>
    <div v-if="tab === 'profile'" class="panel p-6">
      <div class="mb-6 flex items-center gap-4"><span class="grid size-14 place-items-center rounded-2xl bg-[#efedff] text-xl font-extrabold text-[#6758ee]">{{ (name || auth.user.value?.email || 'A').slice(0, 1).toUpperCase() }}</span><div><h2 class="mb-1 text-xl font-extrabold">Личные данные</h2><p class="mb-0 text-sm muted">Используются только внутри вашего кабинета.</p></div></div>
      <div class="space-y-4"><UFormField label="Имя"><UInput v-model="name" size="lg" class="w-full" /></UFormField><UFormField label="Email"><UInput :model-value="auth.user.value?.email" size="lg" disabled class="w-full" /></UFormField><UButton label="Сохранить изменения" size="lg" @click="saveProfile" /></div>
    </div>
    <div v-else class="space-y-3">
      <div class="panel p-5"><div class="flex items-center justify-between gap-4"><div class="flex items-center gap-4"><span class="grid size-12 place-items-center rounded-2xl bg-[#e8f5ff] text-[#229ed9]"><UIcon name="i-simple-icons-telegram" class="size-6" /></span><div><h2 class="mb-1 font-extrabold">Telegram</h2><p class="mb-0 text-sm muted">Получайте готовые отчёты сразу после запуска.</p></div></div><UBadge v-if="linked('telegram')" label="Подключён" color="success" variant="soft" /><UButton v-else to="/auth" label="Подключить" variant="outline" /></div></div>
      <div class="panel p-5"><div class="flex items-center justify-between gap-4"><div class="flex items-center gap-4"><span class="grid size-12 place-items-center rounded-2xl bg-[#f3f3f3]"><UIcon name="i-simple-icons-google" class="size-6" /></span><div><h2 class="mb-1 font-extrabold">Google</h2><p class="mb-0 text-sm muted">Быстрый и безопасный способ входа.</p></div></div><UBadge v-if="linked('google')" label="Подключён" color="success" variant="soft" /><UButton v-else label="Подключить" variant="outline" @click="connectGoogle" /></div></div>
    </div>
  </div>
</template>
