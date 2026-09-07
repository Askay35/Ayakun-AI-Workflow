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
      <div><UButton to="/runs" label="К запускам" icon="i-lucide-arrow-left" variant="link" class="px-0" /><h1 class="text-3xl font-bold">{{ run?.workflow_name || 'Запуск' }}</h1><p class="muted">{{ id }}</p></div>
      <div class="flex items-center gap-2"><UBadge :label="run?.status" size="lg" variant="soft" /><UButton v-if="run && !done(run)" label="Отменить" color="error" variant="outline" @click="cancel" /></div>
    </div>
    <div class="grid gap-4 lg:grid-cols-[1fr_280px]">
      <div class="space-y-3">
        <UCard v-for="node in run?.node_runs" :key="node.id">
          <div class="flex justify-between"><h2 class="font-semibold">Узел {{ node.node_id }}</h2><UBadge :label="node.status" variant="soft" /></div>
          <p v-if="node.output" class="mt-3 whitespace-pre-wrap text-sm">{{ formatOutput(node.output) }}</p>
          <p v-if="node.error" class="mt-3 text-sm text-error">{{ node.error }}</p>
          <div v-if="node.citations?.length" class="mt-3 border-t border-default pt-3"><p class="text-xs font-semibold uppercase muted">Источники</p><a v-for="citation in node.citations" :key="citation.url" :href="citation.url" target="_blank" class="mt-1 block text-sm text-primary hover:underline">{{ citation.title }}</a></div>
        </UCard>
      </div>
      <UCard><p class="muted">Начало</p><p>{{ run && new Date(run.created_at).toLocaleString('ru') }}</p><p class="mt-4 muted">Стоимость</p><p class="text-2xl font-bold">{{ run?.cost?.toLocaleString() || 0 }} токенов</p><p class="mt-4 text-xs muted">Обновления идут через SSE; при недоступности используется polling.</p></UCard>
    </div>
  </div>
</template>
