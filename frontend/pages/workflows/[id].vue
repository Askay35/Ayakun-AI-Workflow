<script setup lang="ts">
import { MarkerType, VueFlow, useVueFlow, type Connection, type EdgeChange, type NodeChange } from '@vue-flow/core'
import { apiErrorMessage } from '~/composables/useApi'
import type { NodeKind, WorkflowNode } from '~/types/api'
import {
  NODE_META,
  canConnect,
  flowEdgesFromNodes,
  linkNodes,
  parseEdgeId,
  removeNode,
  unlinkNodes
} from '~/utils/workflow-graph'

definePageMeta({ layout: 'app', middleware: 'auth', ssr: false })
const route = useRoute()
const api = useApi()
const toast = useToast()
const id = String(route.params.id)
const flowId = `workflow-${id}`

const { data: workflow, error: workflowError } = await useAsyncData(`workflow-${id}`, () => api.workflows.get(id))
if (workflowError.value || !workflow.value) {
  throw createError({ statusCode: 404, statusMessage: 'Цепочка не найдена', fatal: false })
}

const nodes = ref<WorkflowNode[]>(structuredClone(toRaw(workflow.value.draft_graph?.nodes || [])).map(node => ({
  ...node,
  parents: node.parents || [],
  children: node.children || []
})))
const scheduleEnabled = ref(Boolean(workflow.value.schedule_cron))
const schedulePreset = ref(workflow.value.schedule_cron || '0 9 * * *')
const selectedId = ref<string>()
const selected = computed(() => nodes.value.find(node => node.id === selectedId.value))
const validationErrors = ref<string[]>([])
const saveState = ref<'saved' | 'saving' | 'dirty'>('saved')
const estimatedCost = ref(Number(workflow.value.estimated_run_cost || 0))
const { screenToFlowCoordinate, zoomIn, zoomOut, fitView } = useVueFlow({ id: flowId })
let saveTimer: ReturnType<typeof setTimeout> | undefined

const palette = (Object.keys(NODE_META) as NodeKind[]).map(type => ({ type, ...NODE_META[type] }))
const schedulePresets = [
  { label: 'Каждый день в 9:00', value: '0 9 * * *' },
  { label: 'Каждый час', value: '0 * * * *' },
  { label: 'Пн–Пт в 10:00', value: '0 10 * * 1-5' },
  { label: 'Раз в неделю (пн 9:00)', value: '0 9 * * 1' }
]
const qualityModes = [
  { label: 'Быстрый', value: 'simple_text' },
  { label: 'Точный', value: 'complex_text' }
]
const edges = computed(() => flowEdgesFromNodes(nodes.value))
const defaultEdgeOptions = {
  type: 'default',
  markerEnd: MarkerType.ArrowClosed,
  style: { stroke: '#8b82e8', strokeWidth: 2 },
  animated: false
}

const save = async () => {
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, { nodes: nodes.value }, {
      schedule_cron: scheduleEnabled.value ? schedulePreset.value : null,
      schedule_timezone: 'UTC'
    })
    workflow.value = saved
    estimatedCost.value = Number(saved.estimated_run_cost || 0)
    saveState.value = 'saved'
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Черновик не сохранён', color: 'error' })
  }
}
const hydrated = ref(false)
watch([nodes, scheduleEnabled, schedulePreset], () => {
  if (!hydrated.value) return
  saveState.value = 'dirty'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 900)
}, { deep: true })
onMounted(() => { hydrated.value = true })
onBeforeUnmount(() => clearTimeout(saveTimer))

const addNode = (type: NodeKind, position: { x: number; y: number }) => {
  const item = NODE_META[type]
  const node: WorkflowNode = {
    id: crypto.randomUUID(),
    type,
    position,
    parents: [],
    children: [],
    data: {
      label: item.label,
      complexity: type === 'prompt' ? 'simple_text' : undefined
    }
  }
  nodes.value.push(node)
  selectedId.value = node.id
}
const onConnect = (connection: Connection) => {
  if (!connection.source || !connection.target) return
  const source = nodes.value.find(node => node.id === connection.source)
  const target = nodes.value.find(node => node.id === connection.target)
  if (!source || !target) return
  if (!canConnect(source, target)) {
    toast.add({
      title: target.type === 'telegram_send' ? 'Telegram принимает только одну входящую связь' : 'Так соединить нельзя',
      color: 'warning'
    })
    return
  }
  nodes.value = linkNodes(nodes.value, connection.source, connection.target)
}
const isValidConnection = (connection: Connection) => {
  const source = nodes.value.find(node => node.id === connection.source)
  const target = nodes.value.find(node => node.id === connection.target)
  return Boolean(source && target && canConnect(source, target))
}
const onEdgesChange = (changes: EdgeChange[]) => {
  for (const change of changes) {
    if (change.type !== 'remove') continue
    const { source, target } = parseEdgeId(change.id)
    if (source && target) nodes.value = unlinkNodes(nodes.value, source, target)
  }
}
const onNodesChange = (changes: NodeChange[]) => {
  const removed = changes.filter(change => change.type === 'remove').map(change => change.id)
  if (!removed.length) return
  for (const nodeId of removed) nodes.value = removeNode(nodes.value, nodeId)
  if (selectedId.value && removed.includes(selectedId.value)) selectedId.value = undefined
}
const onDragStart = (event: DragEvent, type: NodeKind) => {
  event.dataTransfer?.setData('application/yakun-node', type)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/yakun-node') as NodeKind
  if (!type || !(type in NODE_META)) return
  addNode(type, screenToFlowCoordinate({ x: event.clientX, y: event.clientY }))
}
const addFromPalette = (type: NodeKind) => {
  const origin = screenToFlowCoordinate({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  addNode(type, { x: origin.x + nodes.value.length * 24, y: origin.y + nodes.value.length * 16 })
}
const deleteSelected = () => {
  if (!selectedId.value) return
  nodes.value = removeNode(nodes.value, selectedId.value)
  selectedId.value = undefined
}
const validate = async () => {
  const result = await api.workflows.validate(id)
  validationErrors.value = result.errors
  toast.add({ title: result.valid ? 'Цепочка готова' : 'Есть ошибки', color: result.valid ? 'success' : 'warning' })
  return result.valid
}
const checkGraph = async () => {
  await validate()
}
const publish = async () => {
  await save()
  if (!(await validate())) return
  try {
    workflow.value = await api.workflows.publish(id)
    toast.add({ title: 'Цепочка опубликована', color: 'success' })
  } catch (error) {
    toast.add({
      title: 'Не удалось опубликовать',
      description: apiErrorMessage(error),
      color: 'error'
    })
  }
}
const run = async () => {
  await save()
  const result = await api.workflows.run(id)
  await navigateTo(`/runs/${result.id}`)
}
</script>

<template>
  <div class="workflow-editor">
    <header class="editor-topbar">
      <div class="flex min-w-0 items-center gap-3">
        <UButton to="/workflows" icon="i-lucide-arrow-left" color="neutral" variant="ghost" class="text-white/80 hover:text-white" />
        <div class="min-w-0">
          <h1 class="mb-0 truncate text-[15px] font-extrabold tracking-tight text-white">{{ workflow?.name }}</h1>
          <p class="mb-0 text-[11px] text-white/45">
            {{ saveState === 'saving' ? 'Сохраняем…' : saveState === 'saved' ? 'Черновик сохранён' : 'Несохранённые изменения' }}
          </p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="editor-cost"><UIcon name="i-lucide-coins" />{{ Math.round(estimatedCost).toLocaleString('ru') }} ток.</span>
        <UButton label="Проверить" icon="i-lucide-circle-check" color="neutral" variant="ghost" class="text-white/80" @click="checkGraph" />
        <UButton label="Опубликовать" color="neutral" variant="outline" class="border-white/15 bg-white/5 text-white" @click="publish" />
        <UButton label="Запустить" icon="i-lucide-play" @click="run" />
      </div>
    </header>
    <div class="editor-body">
      <aside class="editor-pane editor-pane-left">
        <p class="editor-kicker">Узлы</p>
        <p class="mb-4 text-[11px] leading-4 text-white/40">Перетащите на холст или кликните, чтобы добавить</p>
        <button
          v-for="item in palette"
          :key="item.type"
          type="button"
          draggable="true"
          class="palette-item"
          @dragstart="onDragStart($event, item.type)"
          @click="addFromPalette(item.type)"
        >
          <span class="palette-icon" :style="{ color: item.accent, background: `${item.accent}22` }">
            <UIcon :name="item.icon" class="size-4" />
          </span>
          <span class="min-w-0 text-left">
            <strong class="block text-[13px] font-extrabold text-white">{{ item.label }}</strong>
            <span class="text-[10px] font-bold uppercase tracking-[0.14em] text-white/35">{{ item.caption }}</span>
          </span>
        </button>
        <div class="editor-schedule">
          <div class="flex items-center justify-between gap-2">
            <p class="mb-0 text-sm font-extrabold text-white">Автозапуск</p>
            <USwitch v-model="scheduleEnabled" />
          </div>
          <p class="mb-0 text-[11px] leading-5 text-white/40">Цепочка стартует сама. Списание только за фактический запуск.</p>
          <USelect
            v-if="scheduleEnabled"
            v-model="schedulePreset"
            :items="schedulePresets"
            value-key="value"
            class="w-full"
          />
        </div>
      </aside>
      <div class="editor-canvas" @dragover.prevent @drop="onDrop">
        <ClientOnly>
          <VueFlow
            :id="flowId"
            v-model:nodes="nodes"
            :edges="edges"
            :default-edge-options="defaultEdgeOptions"
            :is-valid-connection="isValidConnection"
            :snap-to-grid="true"
            :snap-grid="[16, 16]"
            :min-zoom="0.35"
            :max-zoom="1.8"
            fit-view-on-init
            class="editor-flow"
            @connect="onConnect"
            @edges-change="onEdgesChange"
            @nodes-change="onNodesChange"
            @node-click="selectedId = $event.node.id"
            @pane-click="selectedId = undefined"
            @edge-click="selectedId = undefined"
          >
            <template #node-web_search="{ data, selected: active }">
              <WorkflowNodeCard kind="web_search" :data="data" :selected="active" />
            </template>
            <template #node-prompt="{ data, selected: active }">
              <WorkflowNodeCard kind="prompt" :data="data" :selected="active" />
            </template>
            <template #node-telegram_send="{ data, selected: active }">
              <WorkflowNodeCard kind="telegram_send" :data="data" :selected="active" />
            </template>
          </VueFlow>
          <template #fallback>
            <div class="grid h-full place-items-center text-sm text-white/40">Загрузка редактора…</div>
          </template>
        </ClientOnly>
        <div v-if="!nodes.length" class="editor-empty">
          <span class="editor-empty-icon"><UIcon name="i-lucide-workflow" class="size-6" /></span>
          <p class="mb-1 text-sm font-extrabold text-white">Соберите цепочку</p>
          <p class="mb-0 max-w-xs text-center text-xs leading-5 text-white/45">Перетащите «Поиск», «Обработку» или «Telegram» на холст и соедините точки справа налево.</p>
        </div>
        <div class="editor-zoom">
          <button type="button" class="editor-zoom-btn" @click="zoomOut()">−</button>
          <button type="button" class="editor-zoom-btn" @click="fitView({ padding: 0.2 })">
            <UIcon name="i-lucide-scan" class="size-3.5" />
          </button>
          <button type="button" class="editor-zoom-btn" @click="zoomIn()">+</button>
        </div>
      </div>
      <aside class="editor-pane editor-pane-right">
        <template v-if="selected">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="editor-kicker">Узел</p>
              <h2 class="mb-0 text-lg font-extrabold text-white">{{ NODE_META[selected.type].label }}</h2>
            </div>
            <UButton icon="i-lucide-trash-2" color="error" variant="ghost" @click="deleteSelected" />
          </div>
          <div class="mt-5 space-y-4">
            <UFormField label="Название">
              <UInput v-model="selected.data.label" class="w-full" />
            </UFormField>
            <UFormField v-if="selected.type === 'web_search'" label="Что найти">
              <UTextarea v-model="selected.data.query" :rows="7" class="w-full" placeholder="Главные новости рынка за последние сутки" />
            </UFormField>
            <template v-if="selected.type === 'prompt'">
              <UFormField label="Режим">
                <USelect v-model="selected.data.complexity" :items="qualityModes" value-key="value" class="w-full" />
              </UFormField>
              <UFormField label="Инструкция">
                <UTextarea v-model="selected.data.prompt" :rows="7" class="w-full" placeholder="Выдели 5 фактов и сделай краткий вывод" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Текст родительских узлов подставится во вход модели автоматически.</p>
            </template>
            <template v-if="selected.type === 'telegram_send'">
              <UFormField label="Получатель">
                <UInput v-model="selected.data.chat_id" class="w-full" placeholder="Пусто — ваш аккаунт" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Только одна входящая связь, исходящих нет. Уходит текст родителя.</p>
            </template>
          </div>
        </template>
        <div v-else>
          <p class="editor-kicker">Свойства</p>
          <h2 class="mb-2 text-lg font-extrabold text-white">Ничего не выбрано</h2>
          <p class="text-sm leading-6 text-white/45">Кликните узел, чтобы настроить его. Соединяйте выход (справа) со входом (слева).</p>
          <div class="editor-cost-card">
            <p class="mb-1 text-[10px] font-extrabold uppercase tracking-[0.16em] text-white/35">Оценка запуска</p>
            <p class="mb-0 text-3xl font-extrabold text-white">{{ Math.round(estimatedCost).toLocaleString('ru') }}</p>
            <p class="mb-0 mt-1 text-xs text-white/40">токенов за всю цепочку</p>
          </div>
        </div>
        <div v-if="validationErrors.length" class="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-3">
          <h3 class="mb-2 text-sm font-extrabold text-amber-200">Ошибки</h3>
          <ul class="mb-0 list-disc space-y-1 pl-5 text-xs text-amber-100/80">
            <li v-for="err in validationErrors" :key="err">{{ err }}</li>
          </ul>
        </div>
      </aside>
    </div>
  </div>
</template>
