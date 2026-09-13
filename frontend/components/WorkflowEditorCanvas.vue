<script setup lang="ts">
import { ConnectionMode, MarkerType, VueFlow, useVueFlow, type Connection, type Edge, type EdgeChange } from '@vue-flow/core'
import { apiErrorMessage } from '~/composables/useApi'
import { useAuthAsyncData } from '~/composables/useAuthAsyncData'
import type { NodeKind, SearchPeriod, Workflow, WorkflowNode } from '~/types/api'
import { formatCredits } from '~/utils/credits'
import {
  NODE_META,
  DEFAULT_HTTP_REQUEST_JSON,
  IF_ELSE_CONDITION_PLACEHOLDER,
  TELEGRAM_MESSAGE_PLACEHOLDER,
  addLink,
  applyLinks,
  branchFromHandle,
  canConnect,
  dropNodeLinks,
  flowEdgesFromLinks,
  linksFromNodes,
  parseEdgeId,
  removeLink,
  resolveNodeId,
  type GraphLink
} from '~/utils/workflow-graph'

const props = defineProps<{ workflowId: string }>()
const api = useApi()
const toast = useToast()
const id = props.workflowId
const flowId = `workflow-${id}`

const { data: workflow, error: workflowError, status } = await useAuthAsyncData<Workflow>(
  `workflow-${id}`,
  () => api.workflows.get(id)
)
if (status.value === 'error' || !workflow.value) {
  throw createError({
    statusCode: (workflowError.value as any)?.statusCode || 404,
    statusMessage: 'Цепочка не найдена',
    fatal: false
  })
}

const nodes = ref<WorkflowNode[]>(structuredClone(toRaw(workflow.value.draft_graph?.nodes || [])).map((node: WorkflowNode) => ({
  ...node,
  parents: node.parents || [],
  children: node.children || []
})))
const links = ref<GraphLink[]>(linksFromNodes(nodes.value))
const edges = ref<Edge[]>(flowEdgesFromLinks(links.value))
const scheduleEnabled = ref(Boolean(workflow.value.schedule_cron))
const parseSchedule = (cron?: string | null) => {
  const [minute = '0', hour = '9', , , rawDays = '*'] = (cron || '').split(/\s+/)
  const weekdays = rawDays === '*'
    ? [1, 2, 3, 4, 5, 6, 7]
    : rawDays.split(',').map(Number).map(day => day === 0 ? 7 : day).filter(day => day >= 1 && day <= 7)
  return {
    time: `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`,
    weekdays: weekdays.length ? weekdays : [1, 2, 3, 4, 5, 6, 7]
  }
}
const initialSchedule = parseSchedule(workflow.value.schedule_cron)
const scheduleTime = ref(initialSchedule.time)
const scheduleDays = ref(initialSchedule.weekdays)
const scheduleTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const scheduleValid = computed(() => (
  !scheduleEnabled.value
  || (/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(scheduleTime.value) && scheduleDays.value.length > 0)
))
const selectedId = ref<string>()
const selectedEdgeId = ref<string>()
const selected = computed(() => nodes.value.find(node => node.id === selectedId.value))
const validationErrors = ref<string[]>([])
const saveState = ref<'saved' | 'saving' | 'dirty'>('saved')
const estimatedCost = ref(Number(workflow.value.estimated_run_cost || 0))
useAppTitle(computed(() => workflow.value?.name || 'Редактор'))
const {
  screenToFlowCoordinate,
  zoomIn,
  zoomOut,
  fitView
} = useVueFlow({ id: flowId })
let saveTimer: ReturnType<typeof setTimeout> | undefined

const palette = (Object.keys(NODE_META) as NodeKind[]).map(type => ({ type, ...NODE_META[type] }))
const weekdayOptions = [
  { label: 'Пн', value: 1 },
  { label: 'Вт', value: 2 },
  { label: 'Ср', value: 3 },
  { label: 'Чт', value: 4 },
  { label: 'Пт', value: 5 },
  { label: 'Сб', value: 6 },
  { label: 'Вс', value: 7 }
]
const qualityModes = [
  { label: 'Быстрый', value: 'simple_text' },
  { label: 'Точный', value: 'complex_text' }
]
// USelect не принимает пустую строку как значение элемента — используем явный "any".
const searchPeriods = [
  { label: 'Любое время', value: 'any' },
  { label: 'Последний час', value: 'h' },
  { label: 'Последние 24 часа', value: 'd' },
  { label: 'Последняя неделя', value: 'w' },
  { label: 'Последний месяц', value: 'm' },
  { label: 'Последний год', value: 'y' }
]
const selectedPeriod = computed({
  get: () => selected.value?.data.period || 'any',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.period = value === 'any' ? undefined : (value as SearchPeriod)
  }
})
const JSON_EXPRESSION_EXAMPLE = '{{$data[0].price}}'
const IF_ELSE_HELP_EXAMPLES = [
  { code: '{{$data[0].price}} != null', note: 'поле есть и не null' },
  { code: '{{$status}} == "active"', note: 'строка' },
  { code: '{{$score}} >= 0.8', note: 'число' },
  { code: '{{$flag}}', note: 'truthy-проверка' }
] as const
const OUTPUT_FORMAT_PLACEHOLDER = [
  '{',
  '  "userId": "{{id пользователя}}",',
  '  "email": "{{email пользователя}}"',
  '}'
].join('\n')
const selectedInstructions = computed({
  get: () => selected.value?.data.instructions || '',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.instructions = value
  }
})
const selectedOutputFormat = computed({
  get: () => selected.value?.data.output_format || '',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.output_format = value
  }
})
const selectedRequestJson = computed({
  get: () => selected.value?.data.request_json || '',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.request_json = value
  }
})
const selectedCondition = computed({
  get: () => selected.value?.data.condition || '',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.condition = value
  }
})
const selectedTelegramMessage = computed({
  get: () => selected.value?.data.message || '',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.message = value
  }
})
const defaultEdgeOptions = {
  type: 'default',
  markerEnd: MarkerType.ArrowClosed,
  style: { stroke: '#8b82e8', strokeWidth: 2 },
  interactionWidth: 28,
  animated: false
}
const toggleScheduleDay = (day: number) => {
  scheduleDays.value = scheduleDays.value.includes(day)
    ? scheduleDays.value.filter(value => value !== day)
    : [...scheduleDays.value, day].sort((a, b) => a - b)
}

const graphForSave = () => ({ nodes: applyLinks(nodes.value, links.value) })

const save = async () => {
  if (!scheduleValid.value) {
    saveState.value = 'dirty'
    return false
  }
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, graphForSave(), {
      schedule: scheduleEnabled.value
        ? { time: scheduleTime.value, weekdays: scheduleDays.value }
        : null,
      schedule_timezone: scheduleTimezone
    })
    workflow.value = saved
    estimatedCost.value = Number(saved.estimated_run_cost || 0)
    saveState.value = 'saved'
    return true
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Черновик не сохранён', color: 'error' })
    return false
  }
}
const hydrated = ref(false)
watch([nodes, links, scheduleEnabled, scheduleTime, scheduleDays], () => {
  if (!hydrated.value) return
  saveState.value = 'dirty'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 900)
}, { deep: true })
onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  window.removeEventListener('keydown', onEditorKey)
})
const onEditorKey = (event: KeyboardEvent) => {
  if (event.key !== 'Delete' && event.key !== 'Backspace') return
  const tag = (event.target as HTMLElement | null)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
  if (!selectedEdgeId.value) return
  event.preventDefault()
  unlinkSelectedEdge()
}
onMounted(() => {
  hydrated.value = true
  window.addEventListener('keydown', onEditorKey)
})

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
      complexity: type === 'prompt' ? 'simple_text' : undefined,
      instructions: type === 'prompt' ? '' : undefined,
      output_format: type === 'prompt' ? '' : undefined,
      request_json: type === 'http_request' ? DEFAULT_HTTP_REQUEST_JSON : undefined,
      condition: type === 'if_else' ? '' : undefined,
      message: type === 'telegram_send' ? '' : undefined
    }
  }
  nodes.value = [...nodes.value, node]
  selectedId.value = node.id
  selectedEdgeId.value = undefined
}
const connectionEnds = (connection: Connection) => ({
  source: resolveNodeId(nodes.value, connection.source),
  target: resolveNodeId(nodes.value, connection.target),
  branch: branchFromHandle(connection.sourceHandle)
})
const connectBlockedTitle = (targetId: string) => {
  const type = nodes.value.find(node => node.id === targetId)?.type
  if (type === 'telegram_send') return 'Telegram принимает только одну входящую связь'
  if (type === 'http_request') return 'HTTP Request принимает только одну входящую связь'
  if (type === 'if_else') return 'IF ELSE принимает только одну входящую связь'
  return 'Так соединить нельзя'
}
const onConnect = (connection: Connection) => {
  const { source, target, branch } = connectionEnds(connection)
  if (!source || !target) return
  if (!canConnect(nodes.value, links.value, source, target, connection.sourceHandle)) {
    toast.add({
      title: connectBlockedTitle(target),
      color: 'warning'
    })
    return
  }
  links.value = addLink(links.value, source, target, branch)
  edges.value = [...edges.value, {
    ...defaultEdgeOptions,
    id: `${source}-->${target}`,
    source,
    target,
    sourceHandle: branch ? `${source}-${branch}` : `${source}-out`,
    targetHandle: `${target}-in`
  }]
}
const unlinkSelectedEdge = () => {
  const edgeId = selectedEdgeId.value
  if (!edgeId) return
  const { source, target } = parseEdgeId(edgeId)
  if (!source || !target) return
  const next = removeLink(links.value, source, target)
  if (next.length === links.value.length) return
  selectedEdgeId.value = undefined
  edges.value = edges.value.filter(edge => edge.id !== edgeId)
  links.value = next
}
const onEdgesChange = (changes: EdgeChange[]) => {
  for (const change of changes) {
    if (change.type !== 'select') continue
    selectedEdgeId.value = change.selected
      ? change.id
      : (selectedEdgeId.value === change.id ? undefined : selectedEdgeId.value)
  }
}
const onDragStart = (event: DragEvent, type: NodeKind) => {
  event.dataTransfer?.setData('application/ayakun-node', type)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/ayakun-node') as NodeKind
  if (!type || !(type in NODE_META)) return
  addNode(type, screenToFlowCoordinate({ x: event.clientX, y: event.clientY }))
}
const addFromPalette = (type: NodeKind) => {
  const origin = screenToFlowCoordinate({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  addNode(type, { x: origin.x + nodes.value.length * 24, y: origin.y + nodes.value.length * 16 })
}
const deleteSelected = () => {
  if (selectedEdgeId.value) {
    unlinkSelectedEdge()
    return
  }
  if (!selectedId.value) return
  const nodeId = selectedId.value
  links.value = dropNodeLinks(links.value, nodeId)
  edges.value = edges.value.filter(edge => edge.source !== nodeId && edge.target !== nodeId)
  nodes.value = nodes.value.filter(node => node.id !== nodeId)
  selectedId.value = undefined
}
const validate = async () => {
  if (!(await save())) {
    validationErrors.value = ['Укажите время и выберите хотя бы один день автозапуска']
    toast.add({ title: 'Проверьте автозапуск', color: 'warning' })
    return false
  }
  const result = await api.workflows.validate(id)
  validationErrors.value = result.errors
  toast.add({ title: result.valid ? 'Цепочка готова' : 'Есть ошибки', color: result.valid ? 'success' : 'warning' })
  return result.valid
}
const checkGraph = async () => {
  await validate()
}
const publish = async () => {
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
  if (!(await save())) {
    toast.add({ title: 'Проверьте настройки автозапуска', color: 'warning' })
    return
  }
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
        <span class="editor-cost"><UIcon name="i-lucide-coins" />≈ {{ formatCredits(estimatedCost) }} credits</span>
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
          <template v-if="scheduleEnabled">
            <UFormField label="Время">
              <UInput v-model="scheduleTime" type="time" class="w-full" />
            </UFormField>
            <div>
              <p class="mb-2 text-[11px] font-bold text-white/60">Дни недели</p>
              <div class="grid grid-cols-4 gap-1.5">
                <button
                  v-for="day in weekdayOptions"
                  :key="day.value"
                  type="button"
                  class="schedule-day"
                  :class="{ 'is-active': scheduleDays.includes(day.value) }"
                  @click="toggleScheduleDay(day.value)"
                >
                  {{ day.label }}
                </button>
              </div>
              <p v-if="!scheduleValid" class="mb-0 mt-2 text-[11px] text-red-300">Укажите время и выберите хотя бы один день</p>
            </div>
            <p class="mb-0 text-[10px] text-white/35">Часовой пояс: {{ scheduleTimezone }}</p>
          </template>
        </div>
      </aside>
      <div class="editor-canvas" @dragover.prevent @drop="onDrop">
        <ClientOnly>
          <VueFlow
            :id="flowId"
            v-model:nodes="nodes"
            v-model:edges="edges"
            :default-edge-options="defaultEdgeOptions"
            :connection-mode="ConnectionMode.Strict"
            :snap-to-grid="true"
            :snap-grid="[16, 16]"
            :min-zoom="0.35"
            :max-zoom="1.8"
            :edges-focusable="true"
            :elements-selectable="true"
            :delete-key-code="null"
            fit-view-on-init
            class="editor-flow"
            @connect="onConnect"
            @edges-change="onEdgesChange"
            @node-click="selectedId = $event.node.id; selectedEdgeId = undefined"
            @pane-click="selectedId = undefined; selectedEdgeId = undefined"
            @edge-click="selectedEdgeId = $event.edge.id; selectedId = undefined"
          >
            <template #node-web_search="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="web_search" :data="data" :selected="active" />
            </template>
            <template #node-prompt="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="prompt" :data="data" :selected="active" />
            </template>
            <template #node-http_request="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="http_request" :data="data" :selected="active" />
            </template>
            <template #node-if_else="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="if_else" :data="data" :selected="active" />
            </template>
            <template #node-telegram_send="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="telegram_send" :data="data" :selected="active" />
            </template>
          </VueFlow>
          <template #fallback>
            <div class="grid h-full place-items-center text-sm text-white/40">Загрузка редактора…</div>
          </template>
        </ClientOnly>
        <div v-if="!nodes.length" class="editor-empty">
          <span class="editor-empty-icon"><UIcon name="i-lucide-workflow" class="size-6" /></span>
          <p class="mb-1 text-sm font-extrabold text-white">Соберите цепочку</p>
          <p class="mb-0 max-w-xs text-center text-xs leading-5 text-white/45">Перетащите узлы на холст и соедините выход справа со входом слева.</p>
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
        <template v-if="selectedEdgeId">
          <p class="editor-kicker">Связь</p>
          <h2 class="mb-2 text-lg font-extrabold text-white">Стрелка</h2>
          <p class="text-sm leading-6 text-white/45">Delete или кнопка ниже убирает связь. Узлы остаются на холсте.</p>
          <UButton class="mt-4" label="Удалить связь" icon="i-lucide-unlink" color="error" variant="soft" @click="unlinkSelectedEdge" />
        </template>
        <template v-else-if="selected">
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
              <UTextarea v-model="selected.data.query" :rows="7" class="w-full bg-[#232433]" placeholder="Главные новости рынка за последние сутки" />
            </UFormField>
            <UFormField v-if="selected.type === 'web_search'" label="Период">
              <USelect v-model="selectedPeriod" :items="searchPeriods" value-key="value" class="w-full" />
            </UFormField>
            <template v-if="selected.type === 'prompt'">
              <UFormField label="Режим">
                <USelect v-model="selected.data.complexity" :items="qualityModes" value-key="value" class="w-full" />
              </UFormField>
              <UFormField label="Промпт">
                <UTextarea v-model="selected.data.prompt" :rows="7" class="w-full" placeholder="Выдели 5 фактов и сделай краткий вывод" />
              </UFormField>
              <UFormField label="Инструкция">
                <UTextarea v-model="selectedInstructions" :rows="4" class="w-full" placeholder="Отвечай кратко, без вступлений" />
              </UFormField>
              <UFormField label="Формат вывода">
                <UTextarea
                  v-model="selectedOutputFormat"
                  :rows="8"
                  class="w-full font-mono text-xs"
                  :placeholder="OUTPUT_FORMAT_PLACEHOLDER"
                />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Инструкция необязательна и уходит модели как системное сообщение. Если задан формат вывода, модель должна вернуть строго его.</p>
            </template>
            <template v-if="selected.type === 'http_request'">
              <UFormField label="Данные запроса">
                <UTextarea v-model="selectedRequestJson" :rows="14" class="w-full font-mono text-xs" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи (можно без родителей). Подстановки вида {{ JSON_EXPRESSION_EXAMPLE }} читаются от корня вывода предыдущего узла. После подстановки значение должно остаться валидным JSON.</p>
            </template>
            <template v-if="selected.type === 'if_else'">
              <UFormField label="Условие">
                <UTextarea v-model="selectedCondition" :rows="3" class="w-full font-mono text-xs" :placeholder="IF_ELSE_CONDITION_PLACEHOLDER" />
              </UFormField>
              <p class="mb-0 text-xs leading-5 text-white/40">Одна входящая связь, выходы TRUE и FALSE. Дальше уходит та же ветка данных, без изменений.</p>
              <details class="editor-help mt-1! text-xs leading-5 text-white/40">
                <summary class="text-[15px]">Как писать условие</summary>
                <div class="editor-help-body">
                  <p class="mt-1! ml-1">Сравнивайте поля вывода предыдущего узла. Путь в фигурных скобках, например <code>{{ JSON_EXPRESSION_EXAMPLE }}</code>.</p>
                  <p class="mt-1! ml-1"><strong>Операторы:</strong> <code>==</code> <code>!=</code> <code>&gt;</code> <code>&lt;</code> <code>&gt;=</code> <code>&lt;=</code>. Также можно написать только поле — пустое / null / отсутствующее = FALSE.</p>
                  <p class="mt-1! ml-1"><strong>Литералы:</strong> строки в кавычках, числа, <code>true</code>, <code>false</code>, <code>null</code>, <code>undefined</code> (то же, что null).</p>
                  <p class="mt-1! ml-1"><strong>Есть ли поле:</strong> если API не вернул ключ, в условии это <code>null</code> — запуск не падает.</p>
                  <ul>
                    <li v-for="item in IF_ELSE_HELP_EXAMPLES" :key="item.code">
                      <code>{{ item.code }}</code> — {{ item.note }}
                    </li>
                  </ul>
                  <p>Сравнения <code>&gt;</code> / <code>&lt;</code> только для чисел: если поля нет, сначала проверьте <code>!= null</code>.</p>
                </div>
              </details>
            </template>
            <template v-if="selected.type === 'telegram_send'">
              <UFormField label="Получатель">
                <UInput v-model="selected.data.chat_id" class="w-full" placeholder="Пусто — ваш аккаунт" />
              </UFormField>
              <UFormField label="Текст сообщения">
                <UTextarea
                  v-model="selectedTelegramMessage"
                  :rows="6"
                  class="w-full font-mono text-xs"
                  :placeholder="TELEGRAM_MESSAGE_PLACEHOLDER"
                />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи. Если текст пустой, отправится вывод предыдущего узла. Если задан — подстановки вида {{ JSON_EXPRESSION_EXAMPLE }} читаются от корня входных данных; отсутствующее поле останавливает запуск. Исходящие можно вести дальше, но текст детям не передаётся.</p>
            </template>
          </div>
        </template>
        <div v-else>
          <p class="editor-kicker">Свойства</p>
          <h2 class="mb-2 text-lg font-extrabold text-white">Ничего не выбрано</h2>
          <p class="text-sm leading-6 text-white/45">Кликните узел, чтобы настроить его. Соединяйте выход (справа) со входом (слева).</p>
          <div class="editor-cost-card">
            <p class="mb-1 text-[10px] font-extrabold uppercase tracking-[0.16em] text-white/35">Оценка запуска</p>
            <p class="mb-0 text-3xl font-extrabold text-white">≈ {{ formatCredits(estimatedCost) }}</p>
            <p class="mb-0 mt-1 text-xs text-white/40">предварительная оценка стоимости запуска</p>
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
