<script setup lang="ts">
import { statusColor, statusLabel } from '~/utils/run-status'

definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const { data: runs, pending, refresh } = await useAuthAsyncData('runs', () => api.runs.list())
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><p class="eyebrow">Контроль выполнения</p><h1 class="page-title">История запусков</h1><p class="muted">Результаты, ошибки и статус каждой автоматизации.</p></div>
      <UButton label="Обновить" icon="i-lucide-refresh-cw" color="neutral" variant="outline" @click="refresh()" />
    </div>
    <div class="panel p-5">
      <div v-if="pending" class="space-y-3"><USkeleton v-for="i in 5" :key="i" class="h-16" /></div>
      <div v-else-if="runs?.length" class="divide-y divide-default">
        <NuxtLink v-for="run in runs" :key="run.id" :to="`/runs/${run.id}`" class="grid items-center gap-4 py-4 transition hover:translate-x-1 sm:grid-cols-[1fr_140px_180px_24px]">
          <div class="flex items-center gap-3"><span class="grid size-11 shrink-0 place-items-center rounded-xl bg-[#efedff] text-[#6758ee]"><UIcon name="i-lucide-play" /></span><div><p class="mb-0 font-bold">{{ run.workflow_name || 'Запуск цепочки' }}</p><p class="mb-0 mt-1 text-xs muted">ID {{ run.id.slice(0, 8) }}</p></div></div>
          <UBadge :color="statusColor(run.status)" variant="soft" class="w-fit">{{ statusLabel(run.status) }}</UBadge>
          <span class="text-sm muted">{{ new Date(run.created_at).toLocaleString('ru') }}</span>
          <UIcon name="i-lucide-chevron-right" class="muted" />
        </NuxtLink>
      </div>
      <div v-else class="py-14 text-center"><span class="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-[#efedff] text-[#6758ee]"><UIcon name="i-lucide-history" class="size-6" /></span><h2 class="mb-2 text-xl font-bold">Запусков пока нет</h2><p class="mb-5 muted">После первого запуска здесь появится подробная история.</p><UButton to="/workflows" label="Открыть цепочки" /></div>
    </div>
  </div>
</template>
