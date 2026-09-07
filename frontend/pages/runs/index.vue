<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const { data: runs, pending, refresh } = await useAsyncData('runs', () => api.runs.list())
const statusColor = (status: string) => status === 'succeeded' ? 'success' : status === 'failed' ? 'error' : status === 'running' ? 'info' : 'neutral'
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="text-3xl font-bold">Запуски</h1><p class="muted">История выполнения всех цепочек.</p></div><UButton label="Обновить" icon="i-lucide-refresh-cw" color="neutral" variant="outline" @click="refresh()" /></div>
    <UCard>
      <div v-if="pending" class="space-y-3"><USkeleton v-for="i in 5" :key="i" class="h-10" /></div>
      <div v-else-if="runs?.length" class="divide-y divide-default">
        <NuxtLink v-for="run in runs" :key="run.id" :to="`/runs/${run.id}`" class="grid grid-cols-[1fr_130px_180px] items-center gap-3 py-4">
          <div><p class="font-medium">{{ run.workflow_name || `Цепочка ${run.workflow_id}` }}</p><p class="text-xs muted">{{ run.id }}</p></div>
          <UBadge :label="run.status" :color="statusColor(run.status) as any" variant="soft" class="w-fit" />
          <span class="text-sm muted">{{ new Date(run.created_at).toLocaleString('ru') }}</span>
        </NuxtLink>
      </div>
      <p v-else class="py-10 text-center muted">Запусков пока нет.</p>
    </UCard>
  </div>
</template>
