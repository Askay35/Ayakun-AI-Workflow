<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const [{ data: workflows }, { data: runs }, { data: billing }] = await Promise.all([
  useAsyncData('dashboard-workflows', () => api.workflows.list().catch(() => [])),
  useAsyncData('dashboard-runs', () => api.runs.list().catch(() => [])),
  useAsyncData('dashboard-billing', () => api.billing.summary().catch(() => null))
])
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="text-3xl font-bold">Обзор</h1><p class="muted">Что происходит с вашими автоматизациями.</p></div><UButton to="/workflows" label="Новая цепочка" icon="i-lucide-plus" /></div>
    <div class="grid-cards">
      <UCard><p class="muted">Цепочек</p><p class="mt-2 text-3xl font-bold">{{ workflows?.length || 0 }}</p></UCard>
      <UCard><p class="muted">Запусков</p><p class="mt-2 text-3xl font-bold">{{ runs?.length || 0 }}</p></UCard>
      <UCard><p class="muted">Баланс</p><p class="mt-2 text-3xl font-bold">{{ billing?.balance?.toLocaleString() || '—' }} токенов</p></UCard>
    </div>
    <UCard class="mt-6">
      <template #header><div class="flex justify-between"><h2 class="text-xl font-semibold">Последние запуски</h2><UButton to="/runs" label="Все" variant="link" /></div></template>
      <div v-if="runs?.length" class="divide-y divide-default">
        <NuxtLink v-for="run in runs.slice(0, 5)" :key="run.id" :to="`/runs/${run.id}`" class="flex justify-between py-3">
          <span>{{ run.workflow_name || run.workflow_id }}</span><UBadge :label="run.status" variant="soft" />
        </NuxtLink>
      </div>
      <p v-else class="muted">Пока нет запусков. Создайте первую цепочку.</p>
    </UCard>
  </div>
</template>
