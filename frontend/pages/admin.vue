<script setup lang="ts">
import type { AdminConfig, Plan, PricingRate } from '~/types/api'
import { ADMIN_AUTH_KEY, readLocal, writeLocal } from '~/utils/local-session'

definePageMeta({ layout: false, ssr: false })
useHead({ title: 'Администрирование' })

const api = useApi()
const toast = useToast()
const login = ref('')
const password = ref('')
const credentials = ref('')
const loading = ref(false)
const config = ref<AdminConfig>()

const searchRates = computed(() =>
  (config.value?.pricing || []).filter(rate => rate.provider === 'serper')
)

const load = async () => {
  if (!credentials.value) return
  loading.value = true
  try {
    config.value = structuredClone(await api.admin.config(credentials.value))
  } catch {
    credentials.value = ''
    writeLocal(ADMIN_AUTH_KEY, null)
    toast.add({ title: 'Неверный логин или пароль', color: 'error' })
  } finally {
    loading.value = false
  }
}
const signIn = async () => {
  credentials.value = btoa(`${login.value}:${password.value}`)
  writeLocal(ADMIN_AUTH_KEY, credentials.value)
  await load()
}
const signOut = () => {
  credentials.value = ''
  password.value = ''
  config.value = undefined
  writeLocal(ADMIN_AUTH_KEY, null)
}
const saveSearchRate = async (rate: PricingRate) => {
  try {
    Object.assign(rate, await api.admin.updatePricing(credentials.value, rate))
    toast.add({ title: 'Цена поиска сохранена', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось сохранить цену', color: 'error' })
  }
}
const savePlan = async (plan: Plan) => {
  try {
    Object.assign(plan, await api.admin.updatePlan(credentials.value, plan))
    toast.add({ title: 'Тариф сохранён', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось сохранить тариф', color: 'error' })
  }
}
const saveSetting = async (setting: AdminConfig['settings'][number]) => {
  try {
    Object.assign(setting, await api.admin.updateSetting(credentials.value, setting))
    toast.add({ title: 'Настройка сохранена', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось сохранить настройку', color: 'error' })
  }
}

onMounted(() => {
  const fromSession = (() => {
    try { return sessionStorage.getItem(ADMIN_AUTH_KEY) } catch { return null }
  })()
  if (fromSession) {
    writeLocal(ADMIN_AUTH_KEY, fromSession)
    try { sessionStorage.removeItem(ADMIN_AUTH_KEY) } catch { /* ignore */ }
  }
  credentials.value = readLocal(ADMIN_AUTH_KEY) || ''
  if (credentials.value) load()
})
</script>

<template>
  <UApp>
    <main class="admin-page">
      <div class="shell admin-shell">
        <div v-if="!config" class="admin-login panel">
          <p class="eyebrow">Ayakun Admin</p>
          <h1 class="page-title" style="font-size: 34px">Вход в панель</h1>
          <form class="space-y-4" @submit.prevent="signIn">
            <UFormField label="Логин">
              <UInput v-model="login" autocomplete="username" class="w-full" />
            </UFormField>
            <UFormField label="Пароль">
              <UInput v-model="password" type="password" autocomplete="current-password" class="w-full" />
            </UFormField>
            <UButton type="submit" label="Войти" block size="lg" :loading="loading" />
          </form>
        </div>

        <template v-else>
          <header class="page-head">
            <div>
              <p class="eyebrow">Ayakun Admin</p>
              <h1 class="page-title">Тарифы и настройки</h1>
            </div>
            <UButton label="Выйти" color="neutral" variant="soft" @click="signOut" />
          </header>

          <h2 class="admin-section-title">Настройки выполнения</h2>
          <div class="mb-9 grid gap-3 md:grid-cols-2">
            <article v-for="setting in config.settings" :key="setting.key" class="panel admin-card">
              <p class="admin-card-title">{{ setting.description }}</p>
              <p class="admin-card-meta">{{ setting.key }}</p>
              <div class="flex gap-2">
                <UInput
                  :model-value="String(setting.value)"
                  class="flex-1"
                  @update:model-value="setting.value = String($event)"
                />
                <UButton label="Сохранить" variant="soft" @click="saveSetting(setting)" />
              </div>
            </article>
          </div>

          <h2 class="admin-section-title">Поиск</h2>
          <div class="mb-9 grid gap-4 lg:grid-cols-2">
            <article v-for="rate in searchRates" :key="rate.id" class="panel admin-card">
              <div class="mb-5 flex items-center justify-between">
                <div>
                  <strong class="admin-card-title">{{ rate.model }}</strong>
                  <p class="admin-card-meta mb-0">{{ rate.provider }}</p>
                </div>
                <USwitch v-model="rate.active" />
              </div>
              <UFormField label="Стоимость одного поиска, credits">
                <UInput v-model="rate.search_credits" type="number" step="0.001" class="w-full" />
              </UFormField>
              <UButton class="mt-5" label="Сохранить" variant="soft" @click="saveSearchRate(rate)" />
            </article>
          </div>

          <h2 class="admin-section-title">Тарифы</h2>
          <div class="grid gap-4 lg:grid-cols-2">
            <article v-for="plan in config.plans" :key="plan.id" class="panel admin-card">
              <div class="grid gap-3 sm:grid-cols-2">
                <UFormField label="Название"><UInput v-model="plan.name" class="w-full" /></UFormField>
                <UFormField label="Цена"><UInput v-model="plan.price" type="number" step="1" class="w-full" /></UFormField>
                <UFormField label="Credits в тарифе"><UInput v-model="plan.limits.included_credits" type="number" class="w-full" /></UFormField>
                <UFormField label="Лимит одного запуска"><UInput v-model="plan.limits.run_cap_credits" type="number" class="w-full" /></UFormField>
                <UFormField label="Валюта"><UInput v-model="plan.currency" maxlength="3" class="w-full" /></UFormField>
              </div>
              <UButton class="mt-5" label="Сохранить тариф" variant="soft" @click="savePlan(plan)" />
            </article>
          </div>
        </template>
      </div>
    </main>
  </UApp>
</template>
