<script setup lang="ts">
import { useAuthAsyncData } from '~/composables/useAuthAsyncData'
import type { NodeRun, WorkflowRun } from '~/types/api'
import { formatCredits } from '~/utils/credits'
import { statusColor, statusKey, statusLabel } from '~/utils/run-status'
import { NODE_META } from '~/utils/workflow-graph'

definePageMeta({ layout: 'app', middleware: 'auth' })
const route = useRoute()
const api = useApi()
const config = useRuntimeConfig()
const id = String(route.params.id)
const { data: run, refresh } = await useAuthAsyncData(`run-${id}`, () => api.runs.get(id))
useAppTitle(computed(() => run.value?.workflow_name || 'Запуск'))
const isSoloRun = computed(() => Boolean(run.value?.input?._solo))
let stream: AbortController | undefined
let poll: ReturnType<typeof setInterval> | undefined
const done = (value?: WorkflowRun | null) => ['succeeded', 'failed', 'cancelled'].includes(value?.status || '')

const steps = computed(() => run.value?.node_runs || [])
const isStepDone = (step: NodeRun) => {
  const key = statusKey(step.status)
  return key === 'succeeded' || key === 'cancelled' || key === 'failed'
}
const completedCount = computed(() => steps.value.filter(isStepDone).length)
const currentStep = computed(() => steps.value.find(step => statusKey(step.status) === 'running'))
const progress = computed(() => {
  if (!steps.value.length) return 0
  if (statusKey(run.value?.status) === 'succeeded') return 100
  return Math.round((completedCount.value / steps.value.length) * 100)
})
const stepMeta = (step: NodeRun) => NODE_META[step.node_type] || NODE_META.prompt
const stepTitle = (step: NodeRun) => step.label || stepMeta(step).label
const stepIcon = (step: NodeRun) => {
  const key = statusKey(step.status)
  if (key === 'succeeded') return 'i-lucide-check'
  if (key === 'failed') return 'i-lucide-x'
  if (key === 'running') return 'i-lucide-loader-circle'
  if (key === 'cancelled') return 'i-lucide-ban'
  return stepMeta(step).icon
}
const stepDuration = (step: NodeRun) => {
  if (!step.started_at || !step.finished_at) return ''
  const seconds = (new Date(step.finished_at).getTime() - new Date(step.started_at).getTime()) / 1000
  return seconds < 1 ? '< 1 с' : `${seconds.toFixed(seconds < 10 ? 1 : 0)} с`
}
const formatOutput = (step: NodeRun) => {
  const output = step.output
  if (!output) return ''
  if (Array.isArray(output)) return ''
  if (step.node_type === 'if_else') {
    const condition = typeof output.condition === 'string' ? output.condition : ''
    const branch = typeof output.branch === 'string' ? output.branch : ''
    if (condition || branch) {
      return [condition, branch].filter(Boolean).join('\n')
    }
  }
  return output.text || output.answer || JSON.stringify(output, null, 2)
}
const stepHasBody = (step: NodeRun) => Boolean(formatOutput(step) || step.error || step.citations?.length)
const expanded = ref<Record<string, boolean>>({})
const isStepExpanded = (step: NodeRun) => {
  if (!stepHasBody(step)) return false
  if (step.node_id in expanded.value) return expanded.value[step.node_id]
  return true
}
const toggleStep = (step: NodeRun) => {
  if (!stepHasBody(step)) return
  expanded.value = { ...expanded.value, [step.node_id]: !isStepExpanded(step) }
}
watch(currentStep, (step) => {
  if (step) expanded.value = { ...expanded.value, [step.node_id]: true }
})


const startPolling = () => {
  poll ??= setInterval(async () => {
    await refresh()
    if (done(run.value) && poll) clearInterval(poll)
  }, 2000)
}

onMounted(async () => {
  if (done(run.value)) return
  stream = new AbortController()
  try {
    const response = await fetch(`${config.public.apiBase}/workflows/runs/${id}/events`, {
      headers: { Authorization: `Bearer ${api.accessToken.value}` },
      signal: stream.signal
    })
    if (!response.ok || !response.body) throw new Error('SSE unavailable')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done: finished } = await reader.read()
      if (finished) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      if (chunks.some(chunk => chunk.includes('data: '))) await refresh()
      if (done(run.value)) break
    }
  } catch {
    if (!stream.signal.aborted) startPolling()
  }
})
onBeforeUnmount(() => { stream?.abort(); if (poll) clearInterval(poll) })
const cancel = async () => { await api.runs.cancel(id); await refresh() }
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <UButton to="/runs" label="Назад к истории" icon="i-lucide-arrow-left" color="neutral" variant="ghost" class="mb-3 px-2" />
        <p class="eyebrow">Результат выполнения</p>
        <h1 class="page-title">{{ run?.workflow_name || 'Запуск цепочки' }}</h1>
        <p class="text-sm muted">
          ID {{ id }}
          <span v-if="isSoloRun"> · один узел</span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <UBadge :color="statusColor(run?.status)" size="lg" variant="soft">{{ statusLabel(run?.status) }}</UBadge>
        <UButton v-if="run && !done(run)" label="Остановить" color="error" variant="outline" @click="cancel" />
      </div>
    </div>

    <div class="grid gap-5 lg:grid-cols-[1fr_300px]">
      <div class="space-y-3">
        <div v-if="steps.length" class="panel p-5">
          <div class="mb-3 flex items-end justify-between gap-4">
            <div>
              <p class="mb-1 text-xs font-bold uppercase tracking-wider muted">Прогресс</p>
              <p class="mb-0 font-bold">
                {{ completedCount }} из {{ steps.length }} звеньев
                <span v-if="currentStep" class="muted">— сейчас «{{ stepTitle(currentStep) }}»</span>
              </p>
            </div>
            <span class="text-2xl font-extrabold">{{ progress }}%</span>
          </div>
          <div class="run-progress"><span class="run-progress-fill" :style="{ width: `${progress}%` }" /></div>
        </div>

        <div
          v-for="(step, index) in steps"
          :key="step.node_id"
          class="panel p-5"
          :class="{ 'run-step-active': statusKey(step.status) === 'running' }"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 text-left"
            :class="{ 'cursor-pointer': stepHasBody(step) }"
            :aria-expanded="stepHasBody(step) ? isStepExpanded(step) : undefined"
            @click="toggleStep(step)"
          >
            <div class="flex min-w-0 items-center gap-3">
              <span
                class="run-step-icon"
                :style="{ background: `${stepMeta(step).accent}1f`, color: stepMeta(step).accent }"
              >
                <UIcon
                  :name="stepIcon(step)"
                  class="size-4"
                  :class="{ 'animate-spin': statusKey(step.status) === 'running' }"
                />
              </span>
              <div class="min-w-0">
                <p class="mb-0 text-xs font-bold uppercase tracking-wider muted">Шаг {{ index + 1 }} · {{ stepMeta(step).label }}</p>
                <h2 class="mb-0 truncate font-bold">{{ stepTitle(step) }}</h2>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <span v-if="stepDuration(step)" class="text-xs muted">{{ stepDuration(step) }}</span>
              <UBadge :color="statusColor(step.status)" variant="soft">{{ statusLabel(step.status) }}</UBadge>
              <UIcon
                v-if="stepHasBody(step)"
                name="i-lucide-chevron-down"
                class="size-4 muted transition-transform"
                :class="{ 'rotate-180': isStepExpanded(step) }"
              />
            </div>
          </button>
          <div v-if="isStepExpanded(step)" class="mt-4 space-y-4">
            <pre v-if="formatOutput(step)" class="overflow-auto whitespace-pre-wrap rounded-2xl bg-[#f7f6f2] p-4 font-[Manrope] text-sm leading-6">{{ formatOutput(step) }}</pre>
            <p v-if="step.error" class="rounded-xl bg-red-50 p-4 text-sm text-error">{{ step.error }}</p>
            <div v-if="step.citations?.length" class="border-t border-default pt-3">
              <p class="text-xs font-semibold uppercase muted">Источники</p>
              <a
                v-for="citation in step.citations"
                :key="citation.url"
                :href="citation.url"
                target="_blank"
                rel="noopener noreferrer"
                class="mt-1 block text-sm text-primary hover:underline"
              >{{ citation.title }} - {{ citation.date }}</a>
            </div>
          </div>
        </div>

        <p v-if="run?.error" class="panel p-5 text-sm text-error">{{ run.error }}</p>
      </div>

      <aside class="panel h-fit p-5">
        <p class="eyebrow">Сводка</p>
        <p class="mb-1 text-sm muted">Запущено</p>
        <p class="font-bold">{{ run && new Date(run.created_at).toLocaleString('ru') }}</p>
        <div class="my-5 border-t border-(--line)" />
        <p class="mb-1 text-sm muted">Списано</p>
        <p class="mb-0 text-3xl font-extrabold">{{ formatCredits(run?.cost) }}</p>
        <p class="text-sm muted">credits</p>
        <p class="mt-5 mb-0 text-xs leading-5 muted">Списание рассчитано по фактическому использованию.</p>
      </aside>
    </div>
  </div>
</template>
