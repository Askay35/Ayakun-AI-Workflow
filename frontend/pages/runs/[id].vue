<script setup lang="ts">
import type { WorkflowRun } from '~/types/api'
definePageMeta({ layout: 'app', middleware: 'auth' })
const route = useRoute()
const api = useApi()
const config = useRuntimeConfig()
const id = String(route.params.id)
const { data: run, refresh } = await useAsyncData(`run-${id}`, () => api.runs.get(id))
let stream: AbortController | undefined
let poll: ReturnType<typeof setInterval> | undefined
const done = (value?: WorkflowRun | null) => ['succeeded', 'failed', 'cancelled'].includes(value?.status || '')
const statusLabel = (status?: string) => ({
  queued: 'В очереди', running: 'Выполняется', succeeded: 'Готово', failed: 'Ошибка', cancelled: 'Отменён', pending: 'Ожидает'
} as Record<string, string>)[status || ''] || status || '—'
const formatOutput = (output?: Record<string, any>) => {
  if (!output) return ''
  return output.text || output.answer || JSON.stringify(output, null, 2)
}

const startPolling = () => {
  poll ??= setInterval(async () => {
    await refresh()
    if (done(run.value) && poll) clearInterval(poll)
  }, 3000)
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
      for (const chunk of chunks) {
        const data = chunk.split('\n').find(line => line.startsWith('data: '))
        if (data) {
          const status = JSON.parse(data.slice(6)) as WorkflowRun
          run.value = { ...(await api.runs.get(id)), ...status }
        }
      }
      if (done(run.value)) break
    }
  } catch {
    if (!stream.signal.aborted) startPolling()
  }
})
onBeforeUnmount(() => { stream?.abort(); if (poll) clearInterval(poll) })
const cancel = async () => { run.value = await api.runs.cancel(id) }
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><UButton to="/runs" label="Назад к истории" icon="i-lucide-arrow-left" color="neutral" variant="ghost" class="mb-3 px-0" /><p class="eyebrow">Результат выполнения</p><h1 class="page-title">{{ run?.workflow_name || 'Запуск цепочки' }}</h1><p class="text-sm muted">ID {{ id }}</p></div>
      <div class="flex items-center gap-2"><UBadge :label="statusLabel(run?.status)" size="lg" variant="soft" /><UButton v-if="run && !done(run)" label="Остановить" color="error" variant="outline" @click="cancel" /></div>
    </div>
    <div class="grid gap-5 lg:grid-cols-[1fr_300px]">
      <div class="space-y-3">
        <div v-for="(node, index) in run?.node_runs" :key="node.id" class="panel p-5">
          <div class="flex justify-between"><div class="flex items-center gap-3"><span class="grid size-10 place-items-center rounded-xl bg-[#efedff] text-sm font-extrabold text-[#6758ee]">{{ Number(index) + 1 }}</span><div><p class="mb-0 text-xs font-bold uppercase tracking-wider muted">Шаг цепочки</p><h2 class="mb-0 font-bold">{{ node.node_id }}</h2></div></div><UBadge :label="statusLabel(node.status)" variant="soft" /></div>
          <pre v-if="node.output" class="mt-4 overflow-auto whitespace-pre-wrap rounded-2xl bg-[#f7f6f2] p-4 font-[Manrope] text-sm leading-6">{{ formatOutput(node.output) }}</pre>
          <p v-if="node.error" class="mt-4 rounded-xl bg-red-50 p-4 text-sm text-error">{{ node.error }}</p>
          <div v-if="node.citations?.length" class="mt-3 border-t border-default pt-3"><p class="text-xs font-semibold uppercase muted">Источники</p><a v-for="citation in node.citations" :key="citation.url" :href="citation.url" target="_blank" class="mt-1 block text-sm text-primary hover:underline">{{ citation.title }}</a></div>
        </div>
      </div>
      <aside class="panel h-fit p-5"><p class="eyebrow">Сводка</p><p class="mb-1 text-sm muted">Запущено</p><p class="font-bold">{{ run && new Date(run.created_at).toLocaleString('ru') }}</p><div class="my-5 border-t border-[var(--line)]" /><p class="mb-1 text-sm muted">Списано</p><p class="mb-0 text-3xl font-extrabold">{{ run?.cost?.toLocaleString() || 0 }}</p><p class="text-sm muted">токенов</p><p class="mt-5 mb-0 text-xs leading-5 muted">Страница обновляется автоматически, пока цепочка выполняется.</p></aside>
    </div>
  </div>
</template>
