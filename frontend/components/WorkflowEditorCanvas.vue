<script setup lang="ts">
import { ConnectionMode, MarkerType, VueFlow, useVueFlow, type Connection, type Edge, type EdgeChange } from '@vue-flow/core'
import { apiErrorMessage } from '~/composables/useApi'
import { useAuthAsyncData } from '~/composables/useAuthAsyncData'
import type { NodeKind, SearchPeriod, Workflow, WorkflowNode } from '~/types/api'
import { formatCredits } from '~/utils/credits'
import { maxOutputTokensFromCredits, promptMaxCredits } from '~/utils/prompt-max-cost'
import { slotsFromWorkflow, type ScheduleSlot } from '~/utils/schedule'
import {
  definedVariableNames,
  nodeVariableHints,
  recordFromVariables,
  variablesFromRecord,
  type VariableRow
} from '~/utils/workflow-variables'
import {
  NODE_META,
  DEFAULT_HTTP_REQUEST_JSON,
  IF_ELSE_CONDITION_PLACEHOLDER,
  SINGLE_INCOMING_TYPES,
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
const route = useRoute()
const api = useApi()
const auth = useAuth()
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
const scheduleEnabled = ref(Boolean(workflow.value.schedule_cron || workflow.value.next_run_at))
const scheduleSlots = ref<ScheduleSlot[]>(slotsFromWorkflow(workflow.value))
const scheduleTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const scheduleActive = computed(() => scheduleEnabled.value && scheduleSlots.value.length > 0)
const workflowVariables = ref<VariableRow[]>(variablesFromRecord(workflow.value.variables))
const selectedId = ref<string>()
const selectedEdgeId = ref<string>()
const selected = computed(() => nodes.value.find(node => node.id === selectedId.value))
const validationErrors = ref<string[]>([])
const saveState = ref<'saved' | 'saving' | 'dirty'>('saved')
const estimatedCost = ref(Number(workflow.value.estimated_run_cost || 0))
const workflowName = ref(workflow.value.name || '')
const renaming = ref(false)
const nameDraft = ref(workflow.value.name || '')
useAppTitle(computed(() => workflowName.value || workflow.value?.name || 'Редактор'))
const {
  screenToFlowCoordinate,
  zoomIn,
  zoomOut,
  fitView
} = useVueFlow({ id: flowId })
let saveTimer: ReturnType<typeof setTimeout> | undefined

const palette = (Object.keys(NODE_META) as NodeKind[]).map(type => ({ type, ...NODE_META[type] }))
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
const sheetsOperations = [
  { label: 'Читать строки', value: 'read' },
  { label: 'Добавить строки', value: 'append' },
  { label: 'Обновить строки', value: 'update' }
]
const gmailOperations = [
  { label: 'Отправить письмо', value: 'send' },
  { label: 'Получить письма', value: 'list' }
]
const gmailAccounts = computed(() => auth.user.value?.gmail_accounts || [])
const gmailAccountItems = computed(() => gmailAccounts.value.map(item => ({
  label: item.email || `Почта ${item.id}`,
  value: item.id
})))
const selectedGmail = computed(() => {
  const accountId = Number(selected.value?.data?.gmail_account_id || 0)
  return gmailAccounts.value.find(item => item.id === accountId) || null
})
const selectedGmailAccountId = computed<number | undefined>({
  get: () => selected.value?.data?.gmail_account_id ?? undefined,
  set: (value) => {
    if (selected.value?.type === 'gmail') selected.value.data.gmail_account_id = value ?? null
  }
})
const gmailLinking = ref(false)
const sqlEngines = [
  { label: 'PostgreSQL', value: 'postgresql' },
  { label: 'MySQL', value: 'mysql' },
  { label: 'ClickHouse', value: 'clickhouse' }
]
const sqlDsnPlaceholder = computed(() => {
  const engine = selected.value?.data?.engine
  if (engine === 'mysql') return 'mysql://user:pass@host:3306/dbname'
  if (engine === 'clickhouse') return 'clickhouse://user:pass@host:8123/dbname'
  return 'postgresql://user:pass@host:5432/dbname'
})
const transformOperations = [
  { label: 'Select — оставить нужные поля', value: 'select' },
  { label: 'Rename — переименовать поля', value: 'rename' },
  { label: 'Set — добавить или изменить значение', value: 'set' },
  { label: 'Remove — удалить поля', value: 'remove' },
  { label: 'Filter — оставить только нужные элементы', value: 'filter' },
  { label: 'Sort — отсортировать', value: 'sort' },
  { label: 'Map — преобразовать каждый элемент массива', value: 'map' }
]
const sortDirections = [
  { label: 'По возрастанию', value: 'asc' },
  { label: 'По убыванию', value: 'desc' }
]
const runtimeConfig = useRuntimeConfig()
const webhookUrl = computed(() => {
  const token = workflow.value?.webhook_token
  if (!token) return ''
  return `${String(runtimeConfig.public.siteUrl)}${String(runtimeConfig.public.apiBase).replace(/\/$/, '')}/webhooks/${token}`
})
const copyWebhookUrl = async () => {
  if (!webhookUrl.value) return
  await navigator.clipboard.writeText(webhookUrl.value)
  toast.add({ title: 'URL скопирован', color: 'success' })
}
const rotateWebhookToken = async () => {
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, graphForSave(), {
      schedule_slots: scheduleSlots.value.map(({ next_at: _next, ...slot }) => slot),
      schedule_enabled: scheduleActive.value,
      schedule_timezone: scheduleTimezone,
      variables: recordFromVariables(workflowVariables.value),
      rotate_webhook_token: true
    })
    workflow.value = saved
    estimatedCost.value = Number(saved.estimated_run_cost || 0)
    saveState.value = 'saved'
    toast.add({ title: 'Новый ключ вебхука создан', color: 'success' })
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Не удалось обновить ключ', color: 'error' })
  }
}
const selectedPeriod = computed({
  get: () => selected.value?.data.period || 'any',
  set: (value: string) => {
    if (!selected.value) return
    selected.value.data.period = value === 'any' ? undefined : (value as SearchPeriod)
  }
})
const JSON_EXPRESSION_EXAMPLE = '{{$data[0].field}}'
const VARIABLE_NAME_EXAMPLE = '{{name}}'
const VARIABLE_COMPARE_EXAMPLE = '{{count}} == 12'
const WEBHOOK_BODY_EXAMPLE = '{{$body}}'
const ROOT_JSON_EXAMPLE = '{{$}}'
const TELEGRAM_LOOP_EXAMPLE = '{% for item in $data %}{{item.title}}{% endfor %}'
const TRANSFORM_MAP_PLACEHOLDER = '{ "title": "{{$name}}" }'
const TRANSFORM_RENAME_PLACEHOLDER = 'old=new'
const TRANSFORM_SET_PLACEHOLDER = 'status=active'
const formatVariableToken = (name: string) => `{{${name}}}`
const IF_ELSE_HELP_EXAMPLES = [
  { code: '{{$data[0].field}} != null', note: 'поле есть и не null' },
  { code: '{{$status}} == "active"', note: 'строка' },
  { code: '{{count}} == 12', note: 'переменная; строка «12» и число 12 равны' },
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
const selectedMaxRunCredits = computed({
  get: () => {
    if (!selected.value || selected.value.type !== 'prompt') return 0
    const stored = Number(selected.value.data.max_run_credits)
    if (Number.isFinite(stored) && stored > 0) return stored
    return promptMaxCredits(selected.value)
  },
  set: (value: number | string) => {
    if (!selected.value || selected.value.type !== 'prompt') return
    const credits = Math.max(1, Math.round(Number(value) || 1))
    selected.value.data.max_run_credits = credits
    selected.value.data.max_output_tokens = maxOutputTokensFromCredits(selected.value, credits)
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
const selectedAssignments = computed({
  get: () => selected.value?.data.assignments || [],
  set: (value: Array<{ key: string; value: string }>) => {
    if (!selected.value) return
    selected.value.data.assignments = value
  }
})
const definedNames = computed(() => definedVariableNames(workflowVariables.value, nodes.value))
const selectedVariableHints = computed(() => selected.value ? nodeVariableHints(selected.value, definedNames.value) : [])
const hintsFor = (nodeId: string) => {
  const node = nodes.value.find(item => item.id === nodeId)
  return node ? nodeVariableHints(node, definedNames.value) : []
}
const defaultEdgeOptions = {
  type: 'default',
  markerEnd: MarkerType.ArrowClosed,
  style: { stroke: '#8b82e8', strokeWidth: 2 },
  interactionWidth: 28,
  animated: false
}

const graphForSave = () => ({ nodes: applyLinks(nodes.value, links.value) })

const save = async () => {
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, graphForSave(), {
      schedule_slots: scheduleSlots.value.map(({ next_at: _next, ...slot }) => slot),
      schedule_enabled: scheduleActive.value,
      schedule_timezone: scheduleTimezone,
      variables: recordFromVariables(workflowVariables.value)
    })
    workflow.value = saved
    workflowName.value = saved.name
    estimatedCost.value = Number(saved.estimated_run_cost || 0)
    saveState.value = 'saved'
    return true
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Черновик не сохранён', color: 'error' })
    return false
  }
}
const connectGmail = async () => {
  const node = selected.value
  if (!node || node.type !== 'gmail') return
  gmailLinking.value = true
  try {
    const saved = await save()
    if (!saved) return
    const bytes = crypto.getRandomValues(new Uint8Array(64))
    const verifier = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
    const challenge = btoa(String.fromCharCode(...new Uint8Array(digest))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    const redirectUri = `${location.origin}/auth/google/callback`
    sessionStorage.setItem('ayakun_google_verifier', verifier)
    sessionStorage.setItem('ayakun_google_redirect_uri', redirectUri)
    sessionStorage.setItem('ayakun_google_purpose', 'gmail')
    sessionStorage.setItem('ayakun_gmail_workflow', id)
    sessionStorage.setItem('ayakun_gmail_node', node.id)
    const { authorization_url } = await api.auth.googleStart(redirectUri, challenge, 'gmail')
    location.href = authorization_url
  } catch (error: any) {
    toast.add({ title: 'Не удалось войти в Google', description: apiErrorMessage(error, 'Попробуйте ещё раз.'), color: 'error' })
    gmailLinking.value = false
  }
}
const disconnectGmailFromNode = () => {
  if (selected.value?.type === 'gmail') selected.value.data.gmail_account_id = null
}
const startRename = () => {
  nameDraft.value = workflowName.value
  renaming.value = true
}
const cancelRename = () => {
  renaming.value = false
  nameDraft.value = workflowName.value
}
const commitRename = async () => {
  const next = nameDraft.value.trim()
  if (!next) {
    toast.add({ title: 'Укажите название', color: 'error' })
    return
  }
  if (next === workflowName.value) {
    renaming.value = false
    return
  }
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, graphForSave(), {
      name: next,
      schedule_slots: scheduleSlots.value.map(({ next_at: _next, ...slot }) => slot),
      schedule_enabled: scheduleActive.value,
      schedule_timezone: scheduleTimezone,
      variables: recordFromVariables(workflowVariables.value)
    })
    workflow.value = saved
    workflowName.value = saved.name
    nameDraft.value = saved.name
    estimatedCost.value = Number(saved.estimated_run_cost || 0)
    saveState.value = 'saved'
    renaming.value = false
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Не удалось переименовать цепочку', color: 'error' })
  }
}
const hydrated = ref(false)
watch([nodes, links, scheduleEnabled, scheduleSlots, workflowVariables], () => {
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
  event.preventDefault()
  deleteSelected()
}
onMounted(async () => {
  hydrated.value = true
  window.addEventListener('keydown', onEditorKey)
  const accountId = Number(route.query.gmail_account || 0)
  const nodeId = String(route.query.gmail_node || '')
  if (accountId && nodeId) {
    const node = nodes.value.find(item => item.id === nodeId)
    if (node?.type === 'gmail') {
      node.data.gmail_account_id = accountId
      selectedId.value = nodeId
      await save()
    }
    await navigateTo({ path: route.path, query: {} }, { replace: true })
  }
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
      max_output_tokens: type === 'prompt' ? 8000 : undefined,
      instructions: type === 'prompt' ? '' : undefined,
      output_format: type === 'prompt' ? '' : undefined,
      request_json: type === 'http_request' ? DEFAULT_HTTP_REQUEST_JSON : undefined,
      condition: type === 'if_else' ? '' : undefined,
      message: type === 'telegram_send' ? '' : undefined,
      operation: type === 'google_sheets' ? 'read' : type === 'gmail' ? 'send' : type === 'data_transform' ? 'select' : undefined,
      sheet_range: type === 'google_sheets' ? 'Sheet1!A1:Z' : undefined,
      values_json: type === 'google_sheets' ? '[]' : undefined,
      max_results: type === 'gmail' ? 10 : undefined,
      mapping_json: type === 'data_transform' ? '' : undefined,
      sort_direction: type === 'data_transform' ? 'asc' : undefined,
      engine: type === 'sql_query' ? 'postgresql' : undefined,
      query: type === 'sql_query' ? 'SELECT 1 AS ok' : undefined,
      assignments: type === 'prompt' || type === 'http_request' || type === 'google_sheets' || type === 'gmail' || type === 'data_transform' || type === 'sql_query' ? [] : undefined
    }
  }
  nodes.value = [...nodes.value, node]
  selectedId.value = node.id
  selectedEdgeId.value = undefined
  if (type === 'webhook') void save()
}
const connectionEnds = (connection: Connection) => ({
  source: resolveNodeId(nodes.value, connection.source),
  target: resolveNodeId(nodes.value, connection.target),
  branch: branchFromHandle(connection.sourceHandle)
})
const connectBlockedTitle = (targetId: string) => {
  const type = nodes.value.find(node => node.id === targetId)?.type
  if (type === 'webhook') return 'Вебхук запускает цепочку и не принимает входящие связи'
  if (type && SINGLE_INCOMING_TYPES.includes(type)) {
    return `${NODE_META[type].label} принимает только одну входящую связь`
  }
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
  const selectedFlowEdges = edges.value.filter(edge => edge.selected)
  const selectedFlowNodes = nodes.value.filter(node => (node as WorkflowNode & { selected?: boolean }).selected)
  const edgeIds = new Set([
    ...selectedFlowEdges.map(edge => edge.id),
    ...(selectedEdgeId.value ? [selectedEdgeId.value] : [])
  ])
  const nodeIds = new Set([
    ...selectedFlowNodes.map(node => node.id),
    ...(selectedId.value ? [selectedId.value] : [])
  ])
  if (edgeIds.size && !nodeIds.size) {
    for (const edgeId of edgeIds) {
      selectedEdgeId.value = edgeId
      unlinkSelectedEdge()
    }
    return
  }
  if (!nodeIds.size) return
  let nextLinks = links.value
  for (const nodeId of nodeIds) nextLinks = dropNodeLinks(nextLinks, nodeId)
  links.value = nextLinks
  edges.value = edges.value.filter(edge => !nodeIds.has(edge.source) && !nodeIds.has(edge.target) && !edgeIds.has(edge.id))
  nodes.value = nodes.value.filter(node => !nodeIds.has(node.id))
  selectedId.value = undefined
  selectedEdgeId.value = undefined
}
const validate = async () => {
  if (!(await save())) return false
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
  if (!(await save())) return
  const result = await api.workflows.run(id)
  await navigateTo(`/runs/${result.id}`)
}
const soloRunBlocked = computed(() => new Set(workflow.value?.solo_run_blocked_node_types || ['if_else']))
const canSoloRunSelected = computed(() => {
  if (!selected.value) return false
  return !soloRunBlocked.value.has(selected.value.type)
})
const nodeRunLoading = ref(false)
const runSelectedNode = async () => {
  if (!selected.value || !canSoloRunSelected.value) return
  if (!(await save())) return
  nodeRunLoading.value = true
  try {
    const result = await api.workflows.runNode(id, selected.value.id)
    await navigateTo(`/runs/${result.id}`)
  } catch (error) {
    toast.add({
      title: 'Не удалось запустить узел',
      description: apiErrorMessage(error),
      color: 'error'
    })
  } finally {
    nodeRunLoading.value = false
  }
}
</script>

<template>
  <div class="workflow-editor">
    <header class="editor-topbar">
      <div class="flex min-w-0 items-center gap-3">
        <UButton to="/workflows" icon="i-lucide-arrow-left" color="neutral" variant="ghost" class="text-white/80 hover:text-white" />
        <div class="min-w-0">
          <div v-if="renaming" class="flex min-w-0 items-center gap-2">
            <UInput
              v-model="nameDraft"
              autofocus
              size="sm"
              class="editor-name-input min-w-0 w-[min(320px,46vw)]"
              maxlength="160"
              @keyup.enter="commitRename"
              @keyup.escape="cancelRename"
            />
            <UButton icon="i-lucide-check" size="xs" color="neutral" variant="soft" aria-label="Сохранить название" @click="commitRename" />
            <UButton icon="i-lucide-x" size="xs" color="neutral" variant="ghost" class="text-white/70" aria-label="Отменить" @click="cancelRename" />
          </div>
          <button
            v-else
            type="button"
            class="group flex max-w-full items-center gap-1.5 text-left"
            title="Переименовать"
            @click="startRename"
          >
            <h1 class="mb-0 truncate text-[15px] font-extrabold tracking-tight text-white">{{ workflowName }}</h1>
            <UIcon name="i-lucide-pencil" class="size-3.5 shrink-0 text-white/35 transition group-hover:text-white/80" />
          </button>
          <p class="mb-0 text-[11px] text-white/45">
            {{ saveState === 'saving' ? 'Сохраняем…' : saveState === 'saved' ? 'Черновик сохранён' : 'Несохранённые изменения' }}
          </p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="editor-cost"><UIcon name="i-lucide-coins" />до {{ formatCredits(estimatedCost) }} credits</span>
        <UButton label="Проверить" icon="i-lucide-circle-check" color="neutral" variant="ghost" class="text-white/80" @click="checkGraph" />
        <UButton label="Опубликовать" color="neutral" variant="outline" class="border-white/15 bg-white/5 text-white" @click="publish" />
        <UButton label="Запустить" icon="i-lucide-play" @click="run" />
      </div>
    </header>
    <div class="editor-body">
      <aside class="editor-pane editor-pane-left">
        <div class="palette-block">
          <p class="editor-kicker">Узлы</p>
          <p class="mb-3 text-[11px] leading-4 text-white/40">Перетащите на холст или кликните</p>
          <div class="palette-list" role="list">
            <button
              v-for="item in palette"
              :key="item.type"
              type="button"
              draggable="true"
              class="palette-item"
              role="listitem"
              @dragstart="onDragStart($event, item.type)"
              @click="addFromPalette(item.type)"
            >
              <span class="palette-icon" :style="{ color: item.accent, background: `${item.accent}22` }">
                <UIcon :name="item.icon" class="size-4" />
              </span>
              <span class="min-w-0 text-left">
                <strong class="block truncate text-[13px] font-extrabold text-white">{{ item.label }}</strong>
                <span class="block truncate text-[10px] font-bold uppercase tracking-[0.14em] text-white/35">{{ item.caption }}</span>
              </span>
            </button>
          </div>
        </div>
        <WorkflowVariablesPanel v-model:items="workflowVariables" />
        <WorkflowSchedulePanel
          v-model:enabled="scheduleEnabled"
          v-model:slots="scheduleSlots"
          :timezone="scheduleTimezone"
        />
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
              <WorkflowNodeCard :node-id="nodeId" kind="web_search" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-prompt="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="prompt" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-http_request="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="http_request" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-if_else="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="if_else" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-telegram_send="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="telegram_send" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-webhook="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="webhook" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-google_sheets="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="google_sheets" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-gmail="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="gmail" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-data_transform="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="data_transform" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-sql_query="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="sql_query" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
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
            <div class="flex items-center gap-1">
              <UButton
                v-if="canSoloRunSelected"
                icon="i-lucide-play"
                label="Запустить"
                size="sm"
                :loading="nodeRunLoading"
                @click="runSelectedNode"
              />
              <UButton icon="i-lucide-trash-2" color="error" variant="ghost" @click="deleteSelected" />
            </div>
          </div>
          <div class="mt-5 space-y-4">
            <UFormField label="Название">
              <UInput v-model="selected.data.label" class="w-full" />
            </UFormField>
            <UFormField v-if="selected.type === 'web_search'" label="Что найти">
              <UTextarea v-model="selected.data.query" :rows="7" class="w-full" placeholder="Главные новости рынка за последние сутки" />
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
              <p class="text-xs leading-5 text-white/40">Инструкция необязательна и уходит модели как системное сообщение. Если задан формат вывода, модель должна вернуть строго его. Переменные: <code>{{ VARIABLE_NAME_EXAMPLE }}</code>.</p>
              <UFormField label="Максимальная стоимость запуска">
                <UInput v-model="selectedMaxRunCredits" type="number" min="1" step="1" class="w-full" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Меньший лимит может обрезать длинный ответ. Списывается только фактический расход.</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'http_request'">
              <UFormField label="Данные запроса">
                <UTextarea v-model="selectedRequestJson" :rows="14" class="w-full font-mono text-xs" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи. Подстановки вида {{ JSON_EXPRESSION_EXAMPLE }} читаются от корня вывода предыдущего узла, <code>{{ VARIABLE_NAME_EXAMPLE }}</code> — из переменных. После подстановки значение должно остаться валидным JSON.</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'if_else'">
              <UFormField label="Условие">
                <UTextarea v-model="selectedCondition" :rows="3" class="w-full font-mono text-xs" :placeholder="IF_ELSE_CONDITION_PLACEHOLDER" />
              </UFormField>
              <p class="mb-0 text-xs leading-5 text-white/40">Одна входящая связь, выходы TRUE (Условие выполнено) и FALSE (Условие не выполнено). Передает данные дальше, без изменений. Условие с переменной: <code>{{ VARIABLE_COMPARE_EXAMPLE }}</code> (число и строка «12» считаются равными). Условия с входными данными: <code>{{ IF_ELSE_CONDITION_PLACEHOLDER }}</code>.</p>
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
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи. Если текст пустой, отправится весь JSON или текст предыдущего узла. <code>{{ ROOT_JSON_EXAMPLE }}</code> — все входные данные, <code>{{ JSON_EXPRESSION_EXAMPLE }}</code> — поле, <code>{{ VARIABLE_NAME_EXAMPLE }}</code> — переменная цепочки. Цикл: <code>{{ TELEGRAM_LOOP_EXAMPLE }}</code>.</p>
            </template>
            <template v-if="selected.type === 'webhook'">
              <p class="text-xs leading-5 text-white/40">Стартовый узел: внешний сервис вызывает URL методом POST, PUT или PATCH, и цепочка запускается. Тело запроса доступно дальше как <code>{{ WEBHOOK_BODY_EXAMPLE }}</code>.</p>
              <UFormField label="URL вебхука">
                <UInput :model-value="webhookUrl" readonly class="w-full font-mono text-xs" placeholder="Сохраните черновик, чтобы получить URL" />
              </UFormField>
              <div class="flex flex-wrap gap-2">
                <UButton label="Скопировать" icon="i-lucide-copy" color="neutral" variant="outline" :disabled="!webhookUrl" @click="copyWebhookUrl" />
                <UButton label="Новый ключ" icon="i-lucide-refresh-cw" color="neutral" variant="ghost" :disabled="!webhookUrl" @click="rotateWebhookToken" />
              </div>
              <p class="text-xs leading-5 text-white/40">Работает после публикации цепочки. Заголовок Authorization не передаётся в данные узла.</p>
            </template>
            <template v-if="selected.type === 'google_sheets'">
              <UFormField label="Действие">
                <USelect v-model="selected.data.operation" :items="sheetsOperations" value-key="value" class="w-full" />
              </UFormField>
              <UFormField label="ID таблицы">
                <UInput v-model="selected.data.spreadsheet_id" class="w-full font-mono text-xs" placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" />
              </UFormField>
              <UFormField label="Диапазон">
                <UInput v-model="selected.data.sheet_range" class="w-full font-mono text-xs" placeholder="Sheet1!A1:Z" />
              </UFormField>
              <UFormField label="OAuth-токен">
                <UInput v-model="selected.data.access_token" type="password" class="w-full" placeholder="ya29...." />
              </UFormField>
              <UFormField label="API-ключ (только чтение)">
                <UInput v-model="selected.data.api_key" type="password" class="w-full" />
              </UFormField>
              <UFormField label="JSON сервисного аккаунта">
                <UTextarea v-model="selected.data.service_account_json" :rows="6" class="w-full font-mono text-xs" placeholder='{"type":"service_account",...}' />
              </UFormField>
              <UFormField v-if="selected.data.operation !== 'read'" label="Значения строк">
                <UTextarea v-model="selected.data.values_json" :rows="8" class="w-full font-mono text-xs" placeholder='[["Ada", 3]] или [{"name":"Ada","score":3}]' />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи. Чтение возвращает JSON <code>rows</code>. Для записи можно подставить {{ JSON_EXPRESSION_EXAMPLE }} или оставить значения пустыми — тогда возьмутся данные предыдущего узла. Нужен токен, API-ключ или сервисный аккаунт.</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'gmail'">
              <UFormField label="Действие">
                <USelect v-model="selected.data.operation" :items="gmailOperations" value-key="value" class="w-full" />
              </UFormField>
              <div class="rounded-xl border border-white/10 p-3">
                <p class="mb-2 text-xs leading-5 text-white/55">
                  <template v-if="selectedGmail">Письма идут через {{ selectedGmail.email || 'подключённый Google' }}.</template>
                  <template v-else>Войдите в Google — так цепочка сможет читать и отправлять письма с выбранной почты.</template>
                </p>
                <UFormField v-if="gmailAccountItems.length" label="Почта" class="mb-2">
                  <USelect v-model="selectedGmailAccountId" :items="gmailAccountItems" value-key="value" class="w-full" />
                </UFormField>
                <div class="flex flex-wrap gap-2">
                  <UButton
                    :label="selectedGmail ? 'Сменить почту' : 'Войти через Google'"
                    icon="i-simple-icons-google"
                    :loading="gmailLinking"
                    @click="connectGmail"
                  />
                  <UButton v-if="selected.data.gmail_account_id" label="Отключить" variant="outline" color="neutral" @click="disconnectGmailFromNode" />
                </div>
              </div>
              <template v-if="selected.data.operation === 'list'">
                <UFormField label="Поиск писем">
                  <UInput v-model="selected.data.gmail_query" class="w-full" placeholder="is:unread newer_than:1d" />
                </UFormField>
                <UFormField label="Максимум писем">
                  <UInput v-model="selected.data.max_results" type="number" min="1" max="50" class="w-full" />
                </UFormField>
              </template>
              <template v-else>
                <UFormField label="От кого">
                  <UInput v-model="selected.data.from_email" class="w-full" placeholder="Необязательно" />
                </UFormField>
                <UFormField label="Кому">
                  <UInput v-model="selected.data.to" class="w-full" placeholder="ada@example.com" />
                </UFormField>
                <UFormField label="Тема">
                  <UInput v-model="selected.data.subject" class="w-full" />
                </UFormField>
                <UFormField label="Текст письма">
                  <UTextarea v-model="selected.data.body" :rows="6" class="w-full" />
                </UFormField>
              </template>
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи. Подстановки {{ JSON_EXPRESSION_EXAMPLE }} и <code>{{ VARIABLE_NAME_EXAMPLE }}</code>. В каждом звене можно войти в свою Google-почту.</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'data_transform'">
              <UFormField label="Операция">
                <USelect v-model="selected.data.operation" :items="transformOperations" value-key="value" class="w-full" />
              </UFormField>
              <UFormField label="Путь к данным">
                <UInput v-model="selected.data.path" class="w-full font-mono text-xs" placeholder="rows или body.items — пусто = весь вход" />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'select' || selected.data.operation === 'remove'" label="Поля">
                <UInput v-model="selected.data.fields" class="w-full font-mono text-xs" placeholder="id, name, email" />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'rename' || selected.data.operation === 'set' || selected.data.operation === 'map'" :label="selected.data.operation === 'map' ? 'Шаблон элемента' : 'Соответствие полей'">
                <UTextarea
                  v-model="selected.data.mapping_json"
                  :rows="8"
                  class="w-full font-mono text-xs"
                  :placeholder="selected.data.operation === 'rename' ? TRANSFORM_RENAME_PLACEHOLDER : selected.data.operation === 'set' ? TRANSFORM_SET_PLACEHOLDER : TRANSFORM_MAP_PLACEHOLDER"
                />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'filter'" label="Условие">
                <UTextarea v-model="selected.data.condition" :rows="3" class="w-full font-mono text-xs" :placeholder="IF_ELSE_CONDITION_PLACEHOLDER" />
              </UFormField>
              <template v-if="selected.data.operation === 'sort'">
                <UFormField label="Поле сортировки">
                  <UInput v-model="selected.data.sort_field" class="w-full font-mono text-xs" placeholder="score" />
                </UFormField>
                <UFormField label="Направление">
                  <USelect v-model="selected.data.sort_direction" :items="sortDirections" value-key="value" class="w-full" />
                </UFormField>
              </template>
              <p class="text-xs leading-5 text-white/40">Универсальный блок над JSON предыдущего узла. Filter использует тот же синтаксис условий, что IF ELSE. Map применяет шаблон к каждому элементу массива.</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'sql_query'">
              <UFormField label="База данных">
                <USelect v-model="selected.data.engine" :items="sqlEngines" value-key="value" class="w-full" />
              </UFormField>
              <UFormField label="Строка подключения">
                <UInput v-model="selected.data.dsn" type="password" class="w-full font-mono text-xs" :placeholder="sqlDsnPlaceholder" />
              </UFormField>
              <UFormField label="SQL-запрос">
                <UTextarea v-model="selected.data.query" :rows="8" class="w-full font-mono text-xs" placeholder="SELECT id, email FROM users LIMIT 50" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">Не больше одной входящей связи. Результат всегда JSON: <code>{"rows":[...],"row_count":N}</code>. В запросе можно использовать {{ JSON_EXPRESSION_EXAMPLE }} и <code>{{ VARIABLE_NAME_EXAMPLE }}</code>. Подключение идёт к вашей PostgreSQL, MySQL или ClickHouse, не к служебной базе сервиса.</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <ul v-if="selectedVariableHints.some(hint => hint.mark === 'undefined')" class="mb-0 mt-3 space-y-1 text-xs text-amber-200">
              <li v-for="hint in selectedVariableHints.filter(item => item.mark === 'undefined')" :key="hint.name">
                <code>{{ formatVariableToken(hint.name) }}</code> — Переменная пока не определена
              </li>
            </ul>
          </div>
        </template>
        <div v-else>
          <p class="editor-kicker">Свойства</p>
          <h2 class="mb-2 text-lg font-extrabold text-white">Ничего не выбрано</h2>
          <p class="text-sm leading-6 text-white/45">Кликните узел, чтобы настроить его. Соединяйте выход (справа) со входом (слева).</p>
          <div class="editor-cost-card">
            <p class="mb-1 text-[10px] font-extrabold uppercase tracking-[0.16em] text-white/35">Максимум запуска</p>
            <p class="mb-0 text-3xl font-extrabold text-white">до {{ formatCredits(estimatedCost) }}</p>
            <p class="mb-0 mt-1 text-xs text-white/40">верхняя граница; списывается фактический расход</p>
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
