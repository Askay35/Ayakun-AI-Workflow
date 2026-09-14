<script setup lang="ts">
import { formatCredits } from '~/utils/credits'
import { apiErrorMessage } from '~/composables/useApi'

definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const [{ data: summary }, { data: plans }] = await Promise.all([
  useAuthAsyncData('billing', () => api.billing.summary()),
  useAuthAsyncData('billing-plans', () => api.billing.plans())
])
const orderedPlans = computed(() => {
  const rank = { free: 0, starter: 1, pro: 2, max: 3 } as Record<string, number>
  return [...(plans.value || [])].sort((a, b) => (rank[a.code] ?? 9) - (rank[b.code] ?? 9))
})
const planName = (code?: string, fallback?: string) => ({ free: 'Пробный', starter: 'Старт', pro: 'Про', max: 'Макс' } as Record<string, string>)[code || ''] || fallback || 'Пробный'
const checkoutKeys = new Map<number, string>()
const checkoutBusy = ref<number | null>(null)
const checkout = async (planId: number) => {
  if (checkoutBusy.value === planId) return
  checkoutBusy.value = planId
  const key = checkoutKeys.get(planId) ?? crypto.randomUUID()
  checkoutKeys.set(planId, key)
  try {
    const { confirmation_url } = await api.billing.checkout(planId, key)
    if (confirmation_url) location.href = confirmation_url
  } catch (error: any) {
    checkoutKeys.delete(planId)
    toast.add({ title: 'Оплата недоступна', description: apiErrorMessage(error), color: 'error' })
  } finally {
    checkoutBusy.value = null
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">Баланс</p>
        <h1 class="page-title">Пополнение credits</h1>
        <p class="muted">Оплатили пакет — кредиты сразу на балансе, без срока действия.</p>
      </div>
    </div>
    <div class="grid-cards">
      <div class="panel metric-card" style="--card-accent:#c9f169"><p class="mb-0 text-sm font-bold muted">На балансе</p><p class="metric-value">{{ formatCredits(summary?.balance) }}</p><p class="mb-0 mt-1 text-xs muted">credits для запусков</p></div>
      <div class="panel metric-card" style="--card-accent:#ffb681"><p class="mb-0 text-sm font-bold muted">Потрачено за месяц</p><p class="metric-value">{{ formatCredits(summary?.usage_this_month) }}</p><p class="mb-0 mt-1 text-xs muted">credits</p></div>
    </div>
    <div class="mb-4 mt-10"><h2 class="mb-1 text-2xl font-extrabold">Выберите запас credits</h2><p class="mb-0 muted">Списывается фактическая стоимость; оценка запуска приблизительная.</p></div>
    <div class="grid-cards">
      <div v-for="plan in orderedPlans" :key="plan.id" class="panel flex flex-col p-6" :class="{ 'border-violet-500': plan.code === 'starter' }">
        <div class="flex justify-between gap-3">
          <h3 class="text-xl font-extrabold">{{ planName(plan.code, plan.name) }}</h3>
          <span class="font-extrabold">{{ Number(plan.price).toLocaleString('ru') }} ₽</span>
        </div>
        <p class="my-5 text-3xl font-extrabold">{{ Number(plan.limits?.included_credits || 0).toLocaleString('ru') }} <span class="text-sm font-medium muted">credits</span></p>
        <ul class="mb-6 space-y-2 text-sm">
          <li class="flex gap-2"><UIcon name="i-lucide-check" class="text-[#6758ee]" />Любое число цепочек</li>
          <li class="flex gap-2"><UIcon name="i-lucide-check" class="text-[#6758ee]" />Запуски по расписанию</li>
        </ul>
        <UButton
          :label="plan.code === 'free' ? 'Бесплатный пакет' : 'Купить credits'"
          block
          size="lg"
          class="mt-auto"
          :loading="checkoutBusy === plan.id"
          :disabled="plan.code === 'free' || checkoutBusy === plan.id"
          @click="checkout(plan.id)"
        />
      </div>
    </div>
    <div class="panel mt-8 p-6">
      <h2 class="mb-1 text-xl font-extrabold">История баланса</h2>
      <p class="mb-4 text-sm muted">Пополнения и фактические списания за звенья. Резерв на время запуска в историю не попадает.</p>
      <div v-if="summary?.ledger?.length" class="mt-3 divide-y divide-default">
        <div v-for="entry in summary.ledger" :key="entry.id" class="flex justify-between gap-4 py-3">
          <div>
            <p class="mb-0 font-medium">{{ entry.description }}</p>
            <p class="mb-0 mt-1 text-xs muted">{{ new Date(entry.created_at).toLocaleString('ru') }}</p>
          </div>
          <strong class="shrink-0" :class="entry.amount > 0 ? 'text-[#4b3dcc]' : 'text-[#c45c3e]'">
            {{ entry.amount > 0 ? '+' : '' }}{{ formatCredits(entry.amount) }}
          </strong>
        </div>
      </div>
      <p v-else class="mb-0 mt-3 text-sm muted">Пока нет операций с балансом.</p>
    </div>
  </div>
</template>
