<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const [{ data: summary }, { data: plans }] = await Promise.all([
  useAsyncData('billing', () => api.billing.summary()),
  useAsyncData('billing-plans', () => api.billing.plans())
])
const checkout = async (planId: number) => {
  try {
    const { confirmation_url } = await api.billing.checkout(planId)
    if (confirmation_url) location.href = confirmation_url
  } catch (error: any) {
    toast.add({ title: 'Оплата недоступна', description: error?.data?.detail, color: 'error' })
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="text-3xl font-bold">Биллинг</h1><p class="muted">Тариф, внутренние токены и операции.</p></div></div>
    <div class="grid-cards">
      <UCard><p class="muted">Текущий тариф</p><p class="mt-2 text-2xl font-bold">{{ summary?.plan?.name || 'Free' }}</p></UCard>
      <UCard><p class="muted">Баланс</p><p class="mt-2 text-2xl font-bold">{{ summary?.balance.toLocaleString() }} токенов</p></UCard>
      <UCard><p class="muted">Использовано за месяц</p><p class="mt-2 text-2xl font-bold">{{ summary?.usage_this_month.toLocaleString() }}</p></UCard>
    </div>
    <h2 class="mb-3 mt-8 text-xl font-semibold">Тарифы</h2>
    <div class="grid-cards"><UCard v-for="plan in plans" :key="plan.id"><div class="flex justify-between"><h3 class="text-lg font-semibold">{{ plan.name }}</h3><span>{{ Number(plan.price).toLocaleString() }} ₽</span></div><p class="my-3 muted">{{ Number(plan.limits.included_tokens || 0).toLocaleString() }} токенов</p><UButton label="Выбрать и оплатить" block :disabled="plan.id === summary?.plan?.id || plan.code === 'free'" @click="checkout(plan.id)" /></UCard></div>
    <UCard class="mt-8"><template #header><h2 class="font-semibold">Операции</h2></template><div class="divide-y divide-default"><div v-for="entry in summary?.ledger" :key="entry.id" class="flex justify-between py-3"><div><p>{{ entry.description }}</p><p class="text-xs muted">{{ new Date(entry.created_at).toLocaleString('ru') }}</p></div><strong :class="entry.amount > 0 ? 'text-success' : ''">{{ entry.amount > 0 ? '+' : '' }}{{ entry.amount.toLocaleString() }}</strong></div></div></UCard>
  </div>
</template>
