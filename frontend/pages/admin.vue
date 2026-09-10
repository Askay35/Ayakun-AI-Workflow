<script setup lang="ts">
import type { AdminConfig, Plan, PricingRate } from '~/types/api'

definePageMeta({ layout: false, ssr: false })
useHead({ title: 'Администрирование' })

const api = useApi()
const toast = useToast()
const login = ref('')
const password = ref('')
const credentials = ref('')
const loading = ref(false)
const config = ref<AdminConfig>()

const load = async () => {
  if (!credentials.value) return
  loading.value = true
  try {
    config.value = structuredClone(await api.admin.config(credentials.value))
  } catch {
    credentials.value = ''
    sessionStorage.removeItem('yakun_admin_auth')
    toast.add({ title: 'Неверный логин или пароль', color: 'error' })
  } finally {
    loading.value = false
  }
}
const signIn = async () => {
  credentials.value = btoa(`${login.value}:${password.value}`)
  sessionStorage.setItem('yakun_admin_auth', credentials.value)
  await load()
}
const signOut = () => {
  credentials.value = ''
  password.value = ''
  config.value = undefined
  sessionStorage.removeItem('yakun_admin_auth')
}
const saveRate = async (rate: PricingRate) => {
  try {
    Object.assign(rate, await api.admin.updatePricing(credentials.value, rate))
    toast.add({ title: 'Цена сохранена', color: 'success' })
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
  credentials.value = sessionStorage.getItem('yakun_admin_auth') || ''
  if (credentials.value) load()
})
</script>

<template>
  <UApp>
    <main class="min-h-screen bg-[#15161e] px-5 py-10 text-white">
      <div class="mx-auto max-w-6xl">
        <div v-if="!config" class="mx-auto mt-[12vh] max-w-sm rounded-3xl border border-white/10 bg-[#20212b] p-7 shadow-2xl">
          <p class="mb-2 text-xs font-extrabold uppercase tracking-[.18em] text-violet-300">Yakun Admin</p>
          <h1 class="mb-6 text-2xl font-extrabold">Вход в панель</h1>
          <form class="space-y-4" @submit.prevent="signIn">
            <UFormField label="Логин">
              <UInput v-model="login" autocomplete="username" class="w-full" />
            </UFormField>
            <UFormField label="Пароль">
              <UInput v-model="password" type="password" autocomplete="current-password" class="w-full" />
            </UFormField>
            <UButton type="submit" label="Войти" block :loading="loading" />
          </form>
        </div>

        <template v-else>
          <header class="mb-8 flex items-center justify-between gap-4">
            <div>
              <p class="mb-1 text-xs font-extrabold uppercase tracking-[.18em] text-violet-300">Yakun Admin</p>
              <h1 class="mb-0 text-3xl font-extrabold">Billing и цены</h1>
            </div>
            <UButton label="Выйти" color="neutral" variant="ghost" @click="signOut" />
          </header>

          <section class="mb-7 grid gap-3 sm:grid-cols-3">
            <div class="rounded-2xl border border-white/8 bg-[#20212b] p-4">
              <p class="mb-1 text-xs text-white/45">Gross margin</p>
              <strong class="text-xl">{{ config.economics.gross_margin * 100 }}%</strong>
            </div>
            <div class="rounded-2xl border border-white/8 bg-[#20212b] p-4">
              <p class="mb-1 text-xs text-white/45">Себестоимость credit</p>
              <strong class="text-xl">${{ config.economics.provider_cost_usd_per_credit }}</strong>
            </div>
            <div class="rounded-2xl border border-white/8 bg-[#20212b] p-4">
              <p class="mb-1 text-xs text-white/45">Цена credit</p>
              <strong class="text-xl">${{ config.economics.customer_price_usd_per_credit }}</strong>
            </div>
          </section>

          <h2 class="mb-3 text-xl font-extrabold">Настройки выполнения</h2>
          <div class="mb-9 grid gap-3 md:grid-cols-2">
            <article v-for="setting in config.settings" :key="setting.key" class="rounded-2xl border border-white/8 bg-[#20212b] p-5">
              <p class="mb-1 font-bold">{{ setting.description }}</p>
              <p class="mb-3 text-xs text-white/40">{{ setting.key }}</p>
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

          <h2 class="mb-3 text-xl font-extrabold">Провайдеры и модели</h2>
          <div class="mb-9 grid gap-4 lg:grid-cols-2">
            <article v-for="rate in config.pricing" :key="rate.id" class="rounded-2xl border border-white/8 bg-[#20212b] p-5">
              <div class="mb-5 flex items-center justify-between">
                <div><strong>{{ rate.model }}</strong><p class="mb-0 text-xs text-white/40">{{ rate.provider }}</p></div>
                <USwitch v-model="rate.active" />
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <UFormField label="Cache hit / 1K"><UInput v-model="rate.input_cache_hit_credits_per_1k" type="number" step="0.001" /></UFormField>
                <UFormField label="Cache miss / 1K"><UInput v-model="rate.input_cache_miss_credits_per_1k" type="number" step="0.001" /></UFormField>
                <UFormField label="Output / 1K"><UInput v-model="rate.output_credits_per_1k" type="number" step="0.001" /></UFormField>
                <UFormField label="Search / запрос"><UInput v-model="rate.search_credits" type="number" step="0.001" /></UFormField>
              </div>
              <UButton class="mt-5" label="Сохранить цену" variant="soft" @click="saveRate(rate)" />
            </article>
          </div>

          <h2 class="mb-3 text-xl font-extrabold">Тарифы</h2>
          <div class="grid gap-4 lg:grid-cols-2">
            <article v-for="plan in config.plans" :key="plan.id" class="rounded-2xl border border-white/8 bg-[#20212b] p-5">
              <div class="grid gap-3 sm:grid-cols-2">
                <UFormField label="Название"><UInput v-model="plan.name" /></UFormField>
                <UFormField label="Цена"><UInput v-model="plan.price" type="number" step="1" /></UFormField>
                <UFormField label="Credits в тарифе"><UInput v-model="plan.limits.included_credits" type="number" /></UFormField>
                <UFormField label="Run cap"><UInput v-model="plan.limits.run_cap_credits" type="number" /></UFormField>
                <UFormField label="Параллельные запуски"><UInput v-model="plan.limits.parallel_runs" type="number" /></UFormField>
                <UFormField label="Валюта"><UInput v-model="plan.currency" maxlength="3" /></UFormField>
              </div>
              <UButton class="mt-5" label="Сохранить тариф" variant="soft" @click="savePlan(plan)" />
            </article>
          </div>
        </template>
      </div>
    </main>
  </UApp>
</template>
