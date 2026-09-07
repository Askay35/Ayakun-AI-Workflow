<script setup lang="ts">
import type { Plan } from '~/types/api'
const api = useApi()
const fallback: Plan[] = [
  { id: 1, code: 'free', name: 'Старт', price: 0, currency: 'RUB', limits: { workflows: 3, scheduled_workflows: 1, included_tokens: 1000 } },
  { id: 2, code: 'pro', name: 'Про', price: 990, currency: 'RUB', limits: { workflows: 50, scheduled_workflows: 20, included_tokens: 50000 } }
]
const { data: plans } = await useAsyncData('public-plans', () => api.billing.plans().catch(() => fallback))
const featuresFor = (plan: Plan) => [
  `${plan.limits.workflows || 0} цепочек`,
  `${plan.limits.scheduled_workflows || 0} по расписанию`,
  `${plan.limits.included_tokens || 0} токенов`
]
</script>

<template>
  <main class="page">
    <div class="mx-auto mb-10 max-w-xl text-center">
      <h1 class="text-4xl font-bold">Прозрачные тарифы</h1>
      <p class="mt-3 muted">Начните бесплатно и платите только когда автоматизации приносят пользу.</p>
    </div>
    <div class="mx-auto grid max-w-4xl gap-5 md:grid-cols-2">
      <UCard v-for="plan in plans" :key="plan.id">
        <h2 class="text-2xl font-semibold">{{ plan.name }}</h2>
        <p class="my-5 text-4xl font-bold">{{ plan.price ? `${plan.price} ₽` : 'Бесплатно' }}<span v-if="plan.price" class="text-sm font-normal muted"> / месяц</span></p>
        <ul class="space-y-2">
          <li v-for="feature in featuresFor(plan)" :key="feature" class="flex gap-2"><UIcon name="i-lucide-check" class="mt-1 text-primary" />{{ feature }}</li>
        </ul>
        <UButton to="/auth" label="Выбрать" block class="mt-7" :variant="plan.price ? 'solid' : 'outline'" />
      </UCard>
    </div>
  </main>
</template>
