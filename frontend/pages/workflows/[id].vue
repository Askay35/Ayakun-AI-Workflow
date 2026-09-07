<script setup lang="ts">
import { MarkerType, VueFlow, useVueFlow, type Connection } from '@vue-flow/core'
import type { NodeKind, WorkflowEdge, WorkflowNode } from '~/types/api'

definePageMeta({ layout: 'app', middleware: 'auth' })
const route = useRoute()
const api = useApi()
const toast = useToast()
const id = String(route.params.id)
const { data: workflow } = await useAsyncData(`workflow-${id}`, () => api.workflows.get(id))
if (!workflow.value) throw createError({ statusCode: 404, statusMessage: 'Цепочка не найдена' })

const nodes = ref<WorkflowNode[]>(structuredClone(workflow.value.draft_graph?.nodes || []))
const edges = ref<WorkflowEdge[]>(structuredClone(workflow.value.draft_graph?.edges || []))
const selectedId = ref<string>()
const selected = computed(() => nodes.value.find(node => node.id === selectedId.value))
const validationErrors = ref<string[]>([])
const saveState = ref<'saved' | 'saving' | 'dirty'>('saved')
const { addEdges, screenToFlowCoordinate } = useVueFlow()
let saveTimer: ReturnType<typeof setTimeout>

const palette: Array<{ type: NodeKind; label: string; icon: string }> = [
  { type: 'web_search', label: 'Поиск в сети', icon: 'i-lucide-search' },
  { type: 'prompt', label: 'AI-промпт', icon: 'i-lucide-sparkles' },
  { type: 'telegram_send', label: 'Telegram', icon: 'i-lucide-send' }
]
const models = ['qwen-turbo', 'qwen-plus', 'deepseek-chat']

const save = async () => {
  saveState.value = 'saving'
  try {
    await api.workflows.save(id, { nodes: nodes.value, edges: edges.value })
    saveState.value = 'saved'
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Черновик не сохранён', color: 'error' })
  }
}
watch([nodes, edges], () => {
  saveState.value = 'dirty'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 900)
}, { deep: true })
onBeforeUnmount(() => clearTimeout(saveTimer))

const onConnect = (connection: Connection) => addEdges({
  ...connection, id: crypto.randomUUID(), markerEnd: MarkerType.ArrowClosed
})
const onDragStart = (event: DragEvent, type: NodeKind) => event.dataTransfer?.setData('application/yakun-node', type)
const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/yakun-node') as NodeKind
  if (!type) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  const item = palette.find(entry => entry.type === type)!
  const node: WorkflowNode = {
    id: crypto.randomUUID(), type, position,
    data: { label: item.label, model: type === 'prompt' ? models[0] : undefined }
  }
  nodes.value.push(node)
  selectedId.value = node.id
}
const validate = async () => {
  const result = await api.workflows.validate(id)
  validationErrors.value = result.errors
  toast.add({ title: result.valid ? 'Цепочка готова' : 'Есть ошибки', color: result.valid ? 'success' : 'warning' })
  return result.valid
}
const validateClick = async () => { await validate() }
const publish = async () => {
  await save()
  if (await validate()) {
    workflow.value = await api.workflows.publish(id)
    toast.add({ title: 'Цепочка опубликована', color: 'success' })
  }
}
const run = async () => {
  await save()
  const result = await api.workflows.run(id)
  await navigateTo(`/runs/${result.id}`)
}
</script>

<template>
  <div class="flex h-screen min-w-0 flex-col">
    <header class="flex items-center justify-between border-b border-default bg-white px-4 py-3">
      <div class="flex items-center gap-3"><UButton to="/workflows" icon="i-lucide-arrow-left" color="neutral" variant="ghost" /><div><h1 class="font-semibold">{{ workflow?.name }}</h1><p class="text-xs muted">{{ saveState === 'saving' ? 'Сохраняем…' : saveState === 'saved' ? 'Сохранено' : 'Есть изменения' }}</p></div></div>
      <div class="flex gap-2"><UButton label="Проверить" color="neutral" variant="outline" @click="validateClick" /><UButton label="Опубликовать" color="neutral" @click="publish" /><UButton label="Запустить" icon="i-lucide-play" @click="run" /></div>
    </header>
    <div class="grid min-h-0 flex-1 grid-cols-[190px_minmax(0,1fr)_280px]">
      <aside class="border-r border-default bg-white p-3"><p class="mb-3 text-xs font-semibold uppercase muted">Узлы</p><div v-for="item in palette" :key="item.type" draggable="true" class="mb-2 cursor-grab rounded-lg border border-default p-3 text-sm" @dragstart="onDragStart($event, item.type)"><UIcon :name="item.icon" class="mr-2" />{{ item.label }}</div></aside>
      <div class="flow-canvas" @dragover.prevent @drop="onDrop">
        <VueFlow v-model:nodes="nodes" v-model:edges="edges" fit-view-on-init @connect="onConnect" @node-click="selectedId = $event.node.id" @pane-click="selectedId = undefined">
          <template #node-web_search="{ data, selected: active }"><WorkflowNodeCard :data="data" :selected="active" /></template>
          <template #node-prompt="{ data, selected: active }"><WorkflowNodeCard :data="data" :selected="active" /></template>
          <template #node-telegram_send="{ data, selected: active }"><WorkflowNodeCard :data="data" :selected="active" /></template>
        </VueFlow>
      </div>
      <aside class="overflow-y-auto border-l border-default bg-white p-4">
        <template v-if="selected">
          <div class="flex justify-between"><h2 class="font-semibold">Настройки узла</h2><UButton icon="i-lucide-trash-2" color="error" variant="ghost" @click="nodes = nodes.filter(n => n.id !== selectedId); edges = edges.filter(e => e.source !== selectedId && e.target !== selectedId)" /></div>
          <div class="mt-4 space-y-4">
            <UFormField label="Название"><UInput v-model="selected.data.label" class="w-full" /></UFormField>
            <UFormField v-if="selected.type === 'web_search'" label="Поисковый запрос"><UTextarea v-model="selected.data.query" class="w-full" placeholder="Можно использовать {{ input }}" /></UFormField>
            <template v-if="selected.type === 'prompt'"><UFormField label="Модель"><USelect v-model="selected.data.model" :items="models" class="w-full" /></UFormField><UFormField label="Промпт"><UTextarea v-model="selected.data.prompt" :rows="7" class="w-full" placeholder="Обработай: {{ input }}" /></UFormField></template>
            <template v-if="selected.type === 'telegram_send'"><UFormField label="Chat ID (необязательно)"><UInput v-model="selected.data.chat_id" class="w-full" placeholder="Связанный аккаунт" /></UFormField><UFormField label="Текст сообщения"><UTextarea v-model="selected.data.text" :rows="5" class="w-full" placeholder="Результат: {{ nodes.node_id.text }}" /></UFormField></template>
          </div>
        </template>
        <div v-else><h2 class="font-semibold">Инспектор</h2><p class="mt-2 text-sm muted">Выберите узел, чтобы настроить его.</p></div>
        <div v-if="validationErrors.length" class="mt-6"><h3 class="font-semibold text-warning">Ошибки</h3><ul class="mt-2 list-disc pl-5 text-sm"><li v-for="error in validationErrors" :key="error">{{ error }}</li></ul></div>
      </aside>
    </div>
  </div>
</template>
