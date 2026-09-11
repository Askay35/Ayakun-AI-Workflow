<script setup lang="ts">
import { useAuthAsyncData } from '~/composables/useAuthAsyncData'
import { formatCredits } from '~/utils/credits'
import { statusColor, statusLabel } from '~/utils/run-status'

definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const auth = useAuth()
const [{ data: workflows }, { data: runs }, { data: billing }] = await Promise.all([
  useAuthAsyncData('dashboard-workflows', () => api.workflows.list().catch(() => [])),
  useAuthAsyncData('dashboard-runs', () => api.runs.list().catch(() => [])),
  useAuthAsyncData('dashboard-billing', () => api.billing.summary().catch(() => null))
])
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">Рабочее пространство</p>
        <h1 class="page-title">Добрый день<span v-if="auth.user.value?.name">, {{ auth.user.value.name }}</span></h1>
        <p class="muted">Следите за автоматизациями и запускайте новые задачи.</p>
      </div>
      <UButton to="/workflows" label="Собрать цепочку" icon="i-lucide-plus" size="lg" />
    </div>
    <div class="grid-cards">
      <div class="panel metric-card" style="--card-accent:#c9f169">
        <p class="mb-0 text-sm font-bold muted">Цепочки</p>
        <p class="metric-value">{{ workflows?.length || 0 }}</p>
        <p class="mb-0 mt-1 text-xs muted">без ограничений</p>
      </div>
      <div class="panel metric-card" style="--card-accent:#ffb681">
        <p class="mb-0 text-sm font-bold muted">Всего запусков</p>
        <p class="metric-value">{{ runs?.length || 0 }}</p>
        <p class="mb-0 mt-1 text-xs muted">за всё время</p>
      </div>
      <div class="panel metric-card" style="--card-accent:#bdb6ff">
        <p class="mb-0 text-sm font-bold muted">Доступно</p>
        <p class="metric-value">{{ formatCredits(billing?.balance) }}</p>
        <p class="mb-0 mt-1 text-xs muted">credits на балансе</p>
      </div>
    </div>
    <div class="panel mt-6 p-6">
      <div class="mb-3 flex items-center justify-between">
        <div>
          <h2 class="mb-1 text-xl font-extrabold">Последние запуски</h2>
          <p class="mb-0 text-sm muted">Что выполнялось недавно</p>
        </div>
        <UButton to="/runs" label="Вся история" trailing-icon="i-lucide-arrow-right" color="neutral" variant="ghost" />
      </div>
      <div v-if="runs?.length" class="divide-y divide-default">
        <NuxtLink v-for="run in runs.slice(0, 5)" :key="run.id" :to="`/runs/${run.id}`"
          class="flex items-center justify-between py-4">
          <div class="flex items-center gap-3"><span
              class="grid size-10 place-items-center rounded-xl bg-[#efedff] text-[#6758ee]">
              <UIcon name="i-lucide-play" />
            </span>
            <div>
              <p class="mb-0 font-bold">{{ run.workflow_name || 'Запуск цепочки' }}</p>
              <p class="mb-0 mt-1 text-xs muted">{{ new Date(run.created_at).toLocaleString('ru') }}</p>
            </div>
          </div>
          <UBadge :color="statusColor(run.status)" variant="soft">{{ statusLabel(run.status) }}</UBadge>
        </NuxtLink>
      </div>
      <div v-else class="py-12 text-center"><span
          class="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-[#efedff] text-[#6758ee]">
          <UIcon name="i-lucide-zap" class="size-6" />
        </span>
        <h3 class="mb-2 font-bold">Здесь появятся результаты</h3>
        <p class="mb-5 muted">Соберите и запустите первую цепочку.</p>
        <UButton to="/workflows" label="Перейти к цепочкам" />
      </div>
    </div>
  </div>
</template>
