<script setup lang="ts">
import { ConnectionMode, MarkerType, SelectionMode, VueFlow, useVueFlow, type Connection, type Edge, type EdgeChange, type NodeChange } from '@vue-flow/core'
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
import { joinCondition, splitCondition } from '~/utils/condition'
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
const api = useApi()
const toast = useToast()
const { t } = useI18n()
const id = props.workflowId
const flowId = `workflow-${id}`

const { data: workflow, error: workflowError, status } = await useAuthAsyncData<Workflow>(
  `workflow-${id}`,
  () => api.workflows.get(id)
)
const { data: editorWallet } = await useAuthAsyncData(
  `editor-wallet-${id}`,
  () => api.billing.wallet().catch(() => ({ balance: 0, media_unlocked: false }))
)
const mediaUnlocked = computed(() => editorWallet.value == null || Boolean(editorWallet.value.media_unlocked))
const paidMediaTypes = new Set<NodeKind>(['image_generation', 'image_recognition', 'audio_transcription'])
const mediaLocked = (type: NodeKind) => paidMediaTypes.has(type) && !mediaUnlocked.value
if (status.value === 'error' || !workflow.value) {
  throw createError({
    statusCode: (workflowError.value as any)?.statusCode || 404,
    statusMessage: t('editor.notFound'),
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
useAppTitle(computed(() => workflowName.value || workflow.value?.name || t('titles.editor')))
const {
  screenToFlowCoordinate,
  zoomIn,
  zoomOut,
  fitView,
  getSelectedNodes,
  getSelectedEdges
} = useVueFlow({ id: flowId })
const hasSelectedNodes = computed(() => getSelectedNodes.value.length > 0)
let saveTimer: ReturnType<typeof setTimeout> | undefined

const palette = computed(() => (Object.keys(NODE_META) as NodeKind[]).map(type => ({
  type,
  ...NODE_META[type],
  label: t(`nodes.${type}.label`),
  caption: t(`nodes.${type}.caption`)
})))
const qualityModes = computed(() => [
  { label: t('editor.qualityFast'), value: 'simple_text' },
  { label: t('editor.qualityExact'), value: 'complex_text' }
])
// USelect не принимает пустую строку как значение элемента — используем явный "any".
const searchPeriods = computed(() => [
  { label: t('editor.periodAny'), value: 'any' },
  { label: t('editor.periodH'), value: 'h' },
  { label: t('editor.periodD'), value: 'd' },
  { label: t('editor.periodW'), value: 'w' },
  { label: t('editor.periodM'), value: 'm' },
  { label: t('editor.periodY'), value: 'y' }
])
const sheetsOperations = computed(() => [
  { label: t('editor.sheetsRead'), value: 'read' },
  { label: t('editor.sheetsAppend'), value: 'append' },
  { label: t('editor.sheetsUpdate'), value: 'update' }
])
const conditionOperators = [
  { label: '>', value: '>' },
  { label: '<', value: '<' },
  { label: '==', value: '==' },
  { label: '!=', value: '!=' },
  { label: '>=', value: '>=' },
  { label: '<=', value: '<=' }
]
const loopModes = computed(() => [
  { label: t('editor.loopForEach'), value: 'for_each' },
  { label: t('editor.loopTimes'), value: 'times' },
  { label: t('editor.loopWhile'), value: 'while' }
])
const delayUnits = computed(() => [
  { label: t('editor.delaySeconds'), value: 'seconds' },
  { label: t('editor.delayMinutes'), value: 'minutes' }
])
const yandexOperations = computed(() => [
  { label: t('editor.yandexDownload'), value: 'download' },
  { label: t('editor.yandexUpload'), value: 'upload' }
])
const mediaSources = computed(() => [
  { label: t('editor.imageUrl'), value: 'url' },
  { label: t('editor.imageFile'), value: 'file' },
  { label: t('editor.imageUpstream'), value: 'upstream' }
])
const conditionLeft = ref('')
const conditionOperator = ref('==')
const conditionRight = ref('')
let syncingCondition = false
const loadConditionFields = (raw: string) => {
  const parts = splitCondition(raw)
  syncingCondition = true
  conditionLeft.value = parts?.left ?? raw
  conditionOperator.value = parts?.operator ?? '=='
  conditionRight.value = parts?.right ?? ''
  syncingCondition = false
}
watch(() => selected.value?.id, () => {
  if (selected.value?.type !== 'if_else') return
  loadConditionFields(selected.value.data.condition || '')
}, { immediate: true })
watch([conditionLeft, conditionOperator, conditionRight], () => {
  if (syncingCondition || selected.value?.type !== 'if_else') return
  const next = !conditionRight.value.trim() && conditionOperator.value === '=='
    ? conditionLeft.value.trim()
    : joinCondition(conditionLeft.value, conditionOperator.value, conditionRight.value)
  if ((selected.value.data.condition || '') !== next) selected.value.data.condition = next
}, { flush: 'sync' })
const conditionUnparsed = computed(() => {
  const raw = selected.value?.type === 'if_else' ? selected.value.data.condition || '' : ''
  return Boolean(raw.trim()) && splitCondition(raw) === null
})
const readMediaFile = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !selected.value) return
  const max = selected.value.type === 'audio_transcription' ? 6 * 1024 * 1024 : 30 * 1024 * 1024
  if (file.size > max) {
    toast.add({ title: t('editor.fileTooBig'), color: 'warning' })
    input.value = ''
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    if (!selected.value) return
    const result = String(reader.result || '')
    const comma = result.indexOf(',')
    selected.value.data.file_base64 = comma >= 0 ? result.slice(comma + 1) : result
    selected.value.data.filename = file.name
  }
  reader.readAsDataURL(file)
}
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
const transformOperations = computed(() => [
  { label: t('editor.transformSelect'), value: 'select' },
  { label: t('editor.transformRename'), value: 'rename' },
  { label: t('editor.transformSet'), value: 'set' },
  { label: t('editor.transformRemove'), value: 'remove' },
  { label: t('editor.transformFilter'), value: 'filter' },
  { label: t('editor.transformSort'), value: 'sort' },
  { label: t('editor.transformMap'), value: 'map' }
])
const sortDirections = computed(() => [
  { label: t('editor.sortAsc'), value: 'asc' },
  { label: t('editor.sortDesc'), value: 'desc' }
])
const runtimeConfig = useRuntimeConfig()
const webhookUrl = computed(() => {
  const token = workflow.value?.webhook_token
  if (!token) return ''
  return `${String(runtimeConfig.public.siteUrl)}${String(runtimeConfig.public.apiBase).replace(/\/$/, '')}/webhooks/${token}`
})
const copyWebhookUrl = async () => {
  if (!webhookUrl.value) return
  await navigator.clipboard.writeText(webhookUrl.value)
  toast.add({ title: t('editor.urlCopied'), color: 'success' })
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
    toast.add({ title: t('editor.webhookRotated'), color: 'success' })
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: t('editor.webhookRotateError'), color: 'error' })
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
const IF_ELSE_HELP_EXAMPLES = computed(() => [
  { code: '{{$data[0].field}} != null', note: t('editor.ifHelpField') },
  { code: '{{$status}} == "active"', note: t('editor.ifHelpString') },
  { code: '{{count}} == 12', note: t('editor.ifHelpVar') },
  { code: '{{$score}} >= 0.8', note: t('editor.ifHelpNumber') },
  { code: '{{$flag}}', note: t('editor.ifHelpTruthy') }
] )
const OUTPUT_FORMAT_PLACEHOLDER = [
  '{',
  '  "userId": "{{user_id}}",',
  '  "email": "{{user_email}}"',
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
const loopVariableOptions = computed(() =>
  [...definedNames.value].sort().map(name => ({ label: name, value: name }))
)
const selectedVariableHints = computed(() => selected.value ? nodeVariableHints(selected.value, definedNames.value) : [])
const hintsFor = (nodeId: string) => {
  const node = nodes.value.find(item => item.id === nodeId)
  return node ? nodeVariableHints(node, definedNames.value) : []
}
const defaultEdgeOptions = {
  type: 'workflow',
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
  } catch (error) {
    saveState.value = 'dirty'
    toast.add({ title: t('editor.saveError'), description: apiErrorMessage(error), color: 'error' })
    return false
  }
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
    toast.add({ title: t('editor.nameRequired'), color: 'error' })
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
    toast.add({ title: t('editor.renameError'), color: 'error' })
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
})

const addNode = (type: NodeKind, position: { x: number; y: number }) => {
  const node: WorkflowNode = {
    id: crypto.randomUUID(),
    type,
    position,
    parents: [],
    children: [],
    data: {
      label: t(`nodes.${type}.label`),
      complexity: type === 'prompt' ? 'simple_text' : undefined,
      max_output_tokens: type === 'prompt' ? 8000 : undefined,
      instructions: type === 'prompt' ? '' : undefined,
      output_format: type === 'prompt' ? '' : undefined,
      request_json: type === 'http_request' ? DEFAULT_HTTP_REQUEST_JSON : undefined,
      condition: type === 'if_else' ? '' : undefined,
      message: type === 'telegram_send' ? '' : undefined,
      chat_id: type === 'telegram_send' ? '' : undefined,
      bot_token: type === 'telegram_send' ? '' : undefined,
      sheet_range: type === 'google_sheets' ? 'Sheet1!A1:Z' : undefined,
      values_json: type === 'google_sheets' ? '[]' : undefined,
      mapping_json: type === 'data_transform' ? '' : undefined,
      sort_direction: type === 'data_transform' ? 'asc' : undefined,
      engine: type === 'sql_query' ? 'postgresql' : undefined,
      query: type === 'sql_query' ? 'SELECT 1 AS ok' : undefined,
      mode: type === 'loop' ? 'for_each' : undefined,
      source: type === 'loop' ? '' : type === 'image' || type === 'audio_transcription' ? 'url' : undefined,
      times: type === 'loop' ? '1' : undefined,
      while_operator: type === 'loop' ? '==' : undefined,
      while_value: type === 'loop' ? '' : undefined,
      amount: type === 'delay' ? '1' : undefined,
      unit: type === 'delay' ? 'seconds' : undefined,
      operation: type === 'google_sheets' ? 'read' : type === 'data_transform' ? 'select' : type === 'yandex_disk' ? 'download' : undefined,
      remote_path: type === 'yandex_disk' ? '' : undefined,
      token: type === 'yandex_disk' ? '' : undefined,
      prompt: type === 'image_generation' || type === 'image_recognition' || type === 'audio_transcription' ? '' : undefined,
      to: type === 'email' ? '' : undefined,
      subject: type === 'email' ? '' : undefined,
      body: type === 'email' ? '' : undefined,
      assignments: type === 'prompt' || type === 'http_request' || type === 'google_sheets' || type === 'email' || type === 'data_transform' || type === 'sql_query' ? [] : undefined
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
  if (type === 'webhook') return t('editor.webhookNoIn')
  if (type && SINGLE_INCOMING_TYPES.includes(type)) {
    return t('editor.singleIn', { label: t(`nodes.${type}.label`) })
  }
  return t('editor.cannotConnect')
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
const unlinkEdge = (edgeId?: string) => {
  const id = edgeId || selectedEdgeId.value
  if (!id) return
  const { source, target } = parseEdgeId(id)
  if (!source || !target) return
  const next = removeLink(links.value, source, target)
  if (next.length === links.value.length) return
  if (selectedEdgeId.value === id) selectedEdgeId.value = undefined
  edges.value = edges.value.filter(edge => edge.id !== id)
  links.value = next
}
const unlinkSelectedEdge = () => unlinkEdge()
const onNodesChange = (changes: NodeChange[]) => {
  for (const change of changes) {
    if (change.type !== 'select') continue
    if (change.selected) selectedId.value = change.id
    else if (selectedId.value === change.id) selectedId.value = undefined
  }
}
const onEdgesChange = (changes: EdgeChange[]) => {
  for (const change of changes) {
    if (change.type !== 'select') continue
    selectedEdgeId.value = change.selected
      ? change.id
      : (selectedEdgeId.value === change.id ? undefined : selectedEdgeId.value)
  }
}
const refuseLockedMedia = (type: NodeKind) => {
  if (!mediaLocked(type)) return false
  toast.add({ title: t('editor.mediaLocked'), color: 'warning' })
  return true
}
const onDragStart = (event: DragEvent, type: NodeKind) => {
  if (mediaLocked(type)) {
    event.preventDefault()
    return
  }
  event.dataTransfer?.setData('application/ayakun-node', type)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/ayakun-node') as NodeKind
  if (!type || !(type in NODE_META)) return
  if (refuseLockedMedia(type)) return
  addNode(type, screenToFlowCoordinate({ x: event.clientX, y: event.clientY }))
}
const addFromPalette = (type: NodeKind) => {
  if (refuseLockedMedia(type)) return
  const origin = screenToFlowCoordinate({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  addNode(type, { x: origin.x + nodes.value.length * 24, y: origin.y + nodes.value.length * 16 })
}
const deleteSelected = () => {
  const nodeIds = new Set(getSelectedNodes.value.map(node => node.id))
  if (selectedId.value) nodeIds.add(selectedId.value)
  if (nodeIds.size) {
    let nextLinks = links.value
    for (const nodeId of nodeIds) nextLinks = dropNodeLinks(nextLinks, nodeId)
    links.value = nextLinks
    edges.value = edges.value.filter(edge => !nodeIds.has(edge.source) && !nodeIds.has(edge.target))
    nodes.value = nodes.value.filter(node => !nodeIds.has(node.id))
    selectedId.value = undefined
    selectedEdgeId.value = undefined
    return
  }
  const edgeIds = new Set(getSelectedEdges.value.map(edge => edge.id))
  if (selectedEdgeId.value) edgeIds.add(selectedEdgeId.value)
  for (const edgeId of edgeIds) unlinkEdge(edgeId)
}
const validate = async () => {
  if (!(await save())) return false
  const result = await api.workflows.validate(id)
  validationErrors.value = result.errors
  toast.add({ title: result.valid ? t('editor.validateOk') : t('editor.validateFail'), color: result.valid ? 'success' : 'warning' })
  return result.valid
}
const checkGraph = async () => {
  await validate()
}
const publish = async () => {
  if (!(await validate())) return
  try {
    workflow.value = await api.workflows.publish(id)
    toast.add({ title: t('editor.published'), color: 'success' })
  } catch (error) {
    toast.add({
      title: t('editor.publishError'),
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
      title: t('editor.nodeRunError'),
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
            <UButton icon="i-lucide-check" size="xs" color="neutral" variant="soft" :aria-label="t('editor.saveNameAria')" @click="commitRename" />
            <UButton icon="i-lucide-x" size="xs" color="neutral" variant="ghost" class="text-white/70" :aria-label="t('editor.cancelAria')" @click="cancelRename" />
          </div>
          <button
            v-else
            type="button"
            class="group flex max-w-full items-center gap-1.5 text-left"
            :title="t('editor.renameAria')"
            @click="startRename"
          >
            <h1 class="mb-0 truncate text-[15px] font-extrabold tracking-tight text-white">{{ workflowName }}</h1>
            <UIcon name="i-lucide-pencil" class="size-3.5 shrink-0 text-white/35 transition group-hover:text-white/80" />
          </button>
          <p class="mb-0 text-[11px] text-white/45">
            {{ saveState === 'saving' ? t('editor.saving') : saveState === 'saved' ? t('editor.saved') : t('editor.unsaved') }}
          </p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="editor-cost"><UIcon name="i-lucide-coins" />{{ t('editor.costUpTo', { cost: formatCredits(estimatedCost) }) }}</span>
        <UButton :label="t('editor.check')" icon="i-lucide-circle-check" color="neutral" variant="ghost" class="text-white/80" @click="checkGraph" />
        <UButton :label="t('editor.publish')" color="neutral" variant="outline" class="border-white/15 bg-white/5 text-white" @click="publish" />
        <UButton :label="t('editor.run')" icon="i-lucide-play" @click="run" />
      </div>
    </header>
    <div class="editor-body">
      <aside class="editor-pane editor-pane-left">
        <div class="palette-block">
          <p class="editor-kicker">{{ t('editor.nodes') }}</p>
          <p class="mb-3 text-[11px] leading-4 text-white/40">{{ t('editor.nodesHint') }}</p>
          <p v-if="!mediaUnlocked" class="mb-3 text-[11px] leading-4 text-amber-200/80">
            {{ t('editor.mediaLockedHint') }}
            <NuxtLink to="/billing" class="underline">{{ t('editor.mediaLockedLink') }}</NuxtLink>
          </p>
          <div class="palette-list" role="list">
            <button
              v-for="item in palette"
              :key="item.type"
              type="button"
              :draggable="!mediaLocked(item.type)"
              class="palette-item"
              :class="{ 'is-locked': mediaLocked(item.type) }"
              role="listitem"
              @dragstart="onDragStart($event, item.type)"
              @click="addFromPalette(item.type)"
            >
              <span class="palette-icon" :style="{ color: item.accent, background: `${item.accent}22` }">
                <UIcon :name="item.icon" class="size-4" />
              </span>
              <span class="min-w-0 text-left">
                <strong class="block truncate text-[13px] font-extrabold text-white">{{ item.label }}</strong>
                <span class="block truncate text-[10px] font-bold uppercase tracking-[0.14em] text-white/35">{{ mediaLocked(item.type) ? t('editor.mediaLockedShort') : item.caption }}</span>
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
            :selection-mode="SelectionMode.Partial"
            :multi-selection-key-code="['Meta', 'Control', 'Shift']"
            :delete-key-code="null"
            fit-view-on-init
            class="editor-flow"
            @connect="onConnect"
            @nodes-change="onNodesChange"
            @edges-change="onEdgesChange"
            @node-click="selectedId = $event.node.id; selectedEdgeId = undefined"
            @pane-click="selectedId = undefined; selectedEdgeId = undefined"
            @edge-click="selectedEdgeId = $event.edge.id; selectedId = undefined"
          >
            <template #edge-workflow="edgeProps">
              <WorkflowEdge v-bind="edgeProps" @remove="unlinkEdge" />
            </template>
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
            <template #node-email="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="email" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-data_transform="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="data_transform" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-sql_query="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="sql_query" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-loop="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="loop" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-delay="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="delay" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-yandex_disk="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="yandex_disk" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-image_generation="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="image_generation" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-image="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="image" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-image_recognition="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="image_recognition" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
            <template #node-audio_transcription="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" kind="audio_transcription" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
          </VueFlow>
          <template #fallback>
            <div class="grid h-full place-items-center text-sm text-white/40">{{ t('editor.loading') }}</div>
          </template>
        </ClientOnly>
        <div v-if="!nodes.length" class="editor-empty">
          <span class="editor-empty-icon"><UIcon name="i-lucide-workflow" class="size-6" /></span>
          <p class="mb-1 text-sm font-extrabold text-white">{{ t('editor.emptyTitle') }}</p>
          <p class="mb-0 max-w-xs text-center text-xs leading-5 text-white/45">{{ t('editor.emptyText') }}</p>
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
        <template v-if="selectedEdgeId && !hasSelectedNodes">
          <p class="editor-kicker">{{ t('editor.edgeKicker') }}</p>
          <h2 class="mb-2 text-lg font-extrabold text-white">{{ t('editor.edgeTitle') }}</h2>
          <p class="text-sm leading-6 text-white/45">{{ t('editor.edgeHint') }}</p>
          <UButton class="mt-4" :label="t('editor.deleteEdge')" icon="i-lucide-unlink" color="error" variant="soft" @click="unlinkSelectedEdge" />
        </template>
        <template v-else-if="selected">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="editor-kicker">{{ t('editor.nodeKicker') }}</p>
              <h2 class="mb-0 text-lg font-extrabold text-white">{{ t(`nodes.${selected.type}.label`) }}</h2>
            </div>
            <div class="flex items-center gap-1">
              <UButton
                v-if="canSoloRunSelected"
                icon="i-lucide-play"
                :label="t('editor.runNode')"
                size="sm"
                :loading="nodeRunLoading"
                @click="runSelectedNode"
              />
              <UButton icon="i-lucide-trash-2" color="error" variant="ghost" @click="deleteSelected" />
            </div>
          </div>
          <div class="mt-5 space-y-4">
            <UFormField :label="t('editor.fieldName')">
              <UInput v-model="selected.data.label" class="w-full" />
            </UFormField>
            <UFormField v-if="selected.type === 'web_search'" :label="t('editor.searchQuery')">
              <UTextarea v-model="selected.data.query" :rows="7" class="w-full" :placeholder="t('editor.searchPlaceholder')" />
            </UFormField>
            <UFormField v-if="selected.type === 'web_search'" :label="t('editor.period')">
              <USelect v-model="selectedPeriod" :items="searchPeriods" value-key="value" class="w-full" />
            </UFormField>
            <template v-if="selected.type === 'prompt'">
              <UFormField :label="t('editor.mode')">
                <USelect v-model="selected.data.complexity" :items="qualityModes" value-key="value" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.prompt')">
                <UTextarea v-model="selected.data.prompt" :rows="7" class="w-full" :placeholder="t('editor.promptPlaceholder')" />
              </UFormField>
              <UFormField :label="t('editor.instructions')">
                <UTextarea v-model="selectedInstructions" :rows="4" class="w-full" :placeholder="t('editor.instructionsPlaceholder')" />
              </UFormField>
              <UFormField :label="t('editor.outputFormat')">
                <UTextarea
                  v-model="selectedOutputFormat"
                  :rows="8"
                  class="w-full font-mono text-xs"
                  :placeholder="OUTPUT_FORMAT_PLACEHOLDER"
                />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.promptHint', { example: VARIABLE_NAME_EXAMPLE }) }}</p>
              <UFormField :label="t('editor.maxRunCost')">
                <UInput v-model="selectedMaxRunCredits" type="number" min="1" step="1" class="w-full" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.maxRunCostHint') }}</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'http_request'">
              <UFormField :label="t('editor.requestJson')">
                <UTextarea v-model="selectedRequestJson" :rows="14" class="w-full font-mono text-xs" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.httpHint', { json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE }) }}</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'if_else'">
              <UFormField :label="t('editor.conditionLeft')">
                <UInput v-model="conditionLeft" class="w-full font-mono text-xs" :placeholder="IF_ELSE_CONDITION_PLACEHOLDER" />
              </UFormField>
              <UFormField :label="t('editor.conditionOp')">
                <USelect v-model="conditionOperator" :items="conditionOperators" value-key="value" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.conditionRight')">
                <UInput v-model="conditionRight" class="w-full font-mono text-xs" placeholder="0.8" />
              </UFormField>
              <p v-if="conditionUnparsed" class="text-xs leading-5 text-amber-200/80">{{ t('editor.conditionRaw') }}</p>
              <p class="mb-0 text-xs leading-5 text-white/40">{{ t('editor.ifHint', { compare: VARIABLE_COMPARE_EXAMPLE, placeholder: IF_ELSE_CONDITION_PLACEHOLDER }) }}</p>
              <details class="editor-help mt-1! text-xs leading-5 text-white/40">
                <summary class="text-[15px]">{{ t('editor.ifHelpTitle') }}</summary>
                <div class="editor-help-body">
                  <p class="mt-1! ml-1">{{ t('editor.ifHelpCompare', { example: JSON_EXPRESSION_EXAMPLE }) }}</p>
                  <p class="mt-1! ml-1">{{ t('editor.ifHelpOps') }}</p>
                  <p class="mt-1! ml-1">{{ t('editor.ifHelpLits') }}</p>
                  <p class="mt-1! ml-1">{{ t('editor.ifHelpMissing') }}</p>
                  <ul>
                    <li v-for="item in IF_ELSE_HELP_EXAMPLES" :key="item.code">
                      <code>{{ item.code }}</code> — {{ item.note }}
                    </li>
                  </ul>
                  <p>{{ t('editor.ifHelpNumbers') }}</p>
                </div>
              </details>
            </template>
            <template v-if="selected.type === 'telegram_send'">
              <UFormField :label="t('editor.recipient')">
                <UInput v-model="selected.data.chat_id" class="w-full" :placeholder="t('editor.telegramPlaceholder')" />
              </UFormField>
              <UFormField :label="t('editor.botToken')">
                <UInput
                  v-model="selected.data.bot_token"
                  type="password"
                  autocomplete="new-password"
                  class="w-full font-mono text-xs"
                  :placeholder="t('editor.botTokenPlaceholder')"
                />
              </UFormField>
              <UFormField :label="t('editor.messageText')">
                <UTextarea
                  v-model="selectedTelegramMessage"
                  :rows="6"
                  class="w-full font-mono text-xs"
                  :placeholder="TELEGRAM_MESSAGE_PLACEHOLDER"
                />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.telegramHint', { root: ROOT_JSON_EXAMPLE, json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE, loop: TELEGRAM_LOOP_EXAMPLE }) }}</p>
            </template>
            <template v-if="selected.type === 'webhook'">
              <p class="text-xs leading-5 text-white/40">{{ t('editor.webhookIntro', { body: WEBHOOK_BODY_EXAMPLE }) }}</p>
              <UFormField :label="t('editor.webhookUrl')">
                <UInput :model-value="webhookUrl" readonly class="w-full font-mono text-xs" :placeholder="t('editor.webhookUrlPlaceholder')" />
              </UFormField>
              <div class="flex flex-wrap gap-2">
                <UButton :label="t('editor.copy')" icon="i-lucide-copy" color="neutral" variant="outline" :disabled="!webhookUrl" @click="copyWebhookUrl" />
                <UButton :label="t('editor.newKey')" icon="i-lucide-refresh-cw" color="neutral" variant="ghost" :disabled="!webhookUrl" @click="rotateWebhookToken" />
              </div>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.webhookAfter') }}</p>
            </template>
            <template v-if="selected.type === 'google_sheets'">
              <UFormField :label="t('editor.action')">
                <USelect v-model="selected.data.operation" :items="sheetsOperations" value-key="value" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.spreadsheetId')">
                <UInput v-model="selected.data.spreadsheet_id" class="w-full font-mono text-xs" placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" />
              </UFormField>
              <UFormField :label="t('editor.sheetRange')">
                <UInput v-model="selected.data.sheet_range" class="w-full font-mono text-xs" placeholder="Sheet1!A1:Z" />
              </UFormField>
              <UFormField :label="t('editor.oauthToken')">
                <UInput v-model="selected.data.access_token" type="password" class="w-full" placeholder="ya29...." />
              </UFormField>
              <UFormField :label="t('editor.apiKey')">
                <UInput v-model="selected.data.api_key" type="password" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.serviceJson')">
                <UTextarea v-model="selected.data.service_account_json" :rows="6" class="w-full font-mono text-xs" placeholder='{"type":"service_account",...}' />
              </UFormField>
              <UFormField v-if="selected.data.operation !== 'read'" :label="t('editor.rowValues')">
                <UTextarea v-model="selected.data.values_json" :rows="8" class="w-full font-mono text-xs" placeholder='[["Ada", 3]] / [{"name":"Ada","score":3}]' />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.sheetsHint', { json: JSON_EXPRESSION_EXAMPLE }) }}</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'email'">
              <UFormField :label="t('editor.emailTo')">
                <UInput v-model="selected.data.to" class="w-full" placeholder="ada@example.com" />
              </UFormField>
              <UFormField :label="t('editor.emailSubject')">
                <UInput v-model="selected.data.subject" class="w-full" :placeholder="t('editor.emailSubjectPlaceholder')" />
              </UFormField>
              <UFormField :label="t('editor.emailBody')">
                <UTextarea
                  v-model="selected.data.body"
                  :rows="6"
                  class="w-full font-mono text-xs"
                  :placeholder="TELEGRAM_MESSAGE_PLACEHOLDER"
                />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.emailHint', { root: ROOT_JSON_EXAMPLE, json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE, loop: TELEGRAM_LOOP_EXAMPLE }) }}</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'data_transform'">
              <UFormField :label="t('editor.operation')">
                <USelect v-model="selected.data.operation" :items="transformOperations" value-key="value" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.dataPath')">
                <UInput v-model="selected.data.path" class="w-full font-mono text-xs" :placeholder="t('editor.dataPathPlaceholder')" />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'select' || selected.data.operation === 'remove'" :label="t('editor.fields')">
                <UInput v-model="selected.data.fields" class="w-full font-mono text-xs" placeholder="id, name, email" />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'rename' || selected.data.operation === 'set' || selected.data.operation === 'map'" :label="selected.data.operation === 'map' ? t('editor.mapTemplate') : t('editor.fieldMap')">
                <UTextarea
                  v-model="selected.data.mapping_json"
                  :rows="8"
                  class="w-full font-mono text-xs"
                  :placeholder="selected.data.operation === 'rename' ? TRANSFORM_RENAME_PLACEHOLDER : selected.data.operation === 'set' ? TRANSFORM_SET_PLACEHOLDER : TRANSFORM_MAP_PLACEHOLDER"
                />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'filter'" :label="t('editor.condition')">
                <UTextarea v-model="selected.data.condition" :rows="3" class="w-full font-mono text-xs" :placeholder="IF_ELSE_CONDITION_PLACEHOLDER" />
              </UFormField>
              <template v-if="selected.data.operation === 'sort'">
                <UFormField :label="t('editor.sortField')">
                  <UInput v-model="selected.data.sort_field" class="w-full font-mono text-xs" placeholder="score" />
                </UFormField>
                <UFormField :label="t('editor.sortDirection')">
                  <USelect v-model="selected.data.sort_direction" :items="sortDirections" value-key="value" class="w-full" />
                </UFormField>
              </template>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.transformHint') }}</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'sql_query'">
              <UFormField :label="t('editor.database')">
                <USelect v-model="selected.data.engine" :items="sqlEngines" value-key="value" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.dsn')">
                <UInput v-model="selected.data.dsn" type="password" class="w-full font-mono text-xs" :placeholder="sqlDsnPlaceholder" />
              </UFormField>
              <UFormField :label="t('editor.sqlQuery')">
                <UTextarea v-model="selected.data.query" :rows="8" class="w-full font-mono text-xs" placeholder="SELECT id, email FROM users LIMIT 50" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.sqlHint', { json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE }) }}</p>
              <WorkflowVariableAssignments v-model:items="selectedAssignments" />
            </template>
            <template v-if="selected.type === 'loop'">
              <UFormField :label="t('editor.loopMode')">
                <USelect v-model="selected.data.mode" :items="loopModes" value-key="value" class="w-full" />
              </UFormField>
              <UFormField v-if="selected.data.mode !== 'times' && selected.data.mode !== 'while'" :label="t('editor.loopSource')">
                <UInput v-model="selected.data.source" class="w-full font-mono text-xs" :placeholder="t('editor.loopSourcePlaceholder')" />
              </UFormField>
              <UFormField v-if="selected.data.mode === 'times'" :label="t('editor.loopTimesLabel')">
                <UInput v-model="selected.data.times" class="w-full font-mono text-xs" :placeholder="t('editor.loopTimesPlaceholder')" />
              </UFormField>
              <template v-if="selected.data.mode === 'while'">
                <UFormField :label="t('editor.loopVariable')">
                  <USelect
                    v-if="loopVariableOptions.length"
                    v-model="selected.data.while_variable"
                    :items="loopVariableOptions"
                    value-key="value"
                    class="w-full"
                  />
                  <p v-else class="text-xs text-white/45">{{ t('editor.loopNoVars') }}</p>
                </UFormField>
                <UFormField :label="t('editor.conditionOp')">
                  <USelect v-model="selected.data.while_operator" :items="conditionOperators" value-key="value" class="w-full" />
                </UFormField>
                <UFormField :label="t('editor.loopValue')">
                  <UInput v-model="selected.data.while_value" class="w-full font-mono text-xs" placeholder="0" />
                </UFormField>
              </template>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.loopHint') }}</p>
            </template>
            <template v-if="selected.type === 'delay'">
              <UFormField :label="t('editor.delayAmount')">
                <UInput v-model="selected.data.amount" class="w-full font-mono text-xs" placeholder="0.35" />
              </UFormField>
              <UFormField :label="t('editor.delayUnit')">
                <USelect v-model="selected.data.unit" :items="delayUnits" value-key="value" class="w-full" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.delayHint') }}</p>
            </template>
            <template v-if="selected.type === 'yandex_disk'">
              <UFormField :label="t('editor.action')">
                <USelect v-model="selected.data.operation" :items="yandexOperations" value-key="value" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.yandexToken')">
                <UInput v-model="selected.data.token" type="password" autocomplete="new-password" class="w-full" />
              </UFormField>
              <UFormField :label="t('editor.yandexRemote')">
                <UInput v-model="selected.data.remote_path" class="w-full font-mono text-xs" placeholder="/folder/{{name}}.jpg" />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'upload'" :label="t('editor.yandexLocal')">
                <UInput v-model="selected.data.local_path" class="w-full font-mono text-xs" :placeholder="t('editor.yandexLocalPlaceholder')" />
              </UFormField>
              <UFormField v-if="selected.data.operation === 'upload'" :label="t('editor.yandexContent')">
                <UTextarea v-model="selected.data.content" :rows="4" class="w-full font-mono text-xs" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.yandexHint') }}</p>
            </template>
            <template v-if="selected.type === 'image_generation'">
              <p v-if="mediaLocked('image_generation')" class="text-xs leading-5 text-amber-200">{{ t('editor.mediaLockedHint') }}</p>
              <UFormField :label="t('editor.imagePrompt')">
                <UTextarea v-model="selected.data.prompt" :rows="6" class="w-full" :placeholder="t('editor.imagePromptPlaceholder')" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.imageCredits') }} {{ t('editor.mediaHint') }}</p>
            </template>
            <template v-if="selected.type === 'image'">
              <UFormField :label="t('editor.imageSource')">
                <USelect v-model="selected.data.source" :items="mediaSources" value-key="value" class="w-full" />
              </UFormField>
              <UFormField v-if="selected.data.source === 'url'" :label="t('editor.imageUrlLabel')">
                <UInput v-model="selected.data.url" class="w-full font-mono text-xs" :placeholder="t('editor.imageUrlPlaceholder')" />
              </UFormField>
              <UFormField v-if="selected.data.source === 'file'" :label="t('editor.imageFileLabel')">
                <input type="file" accept="image/*" class="block w-full text-xs text-white/70" @change="readMediaFile">
                <p v-if="selected.data.filename" class="mt-1 text-xs text-white/50">{{ selected.data.filename }}</p>
              </UFormField>
              <p v-if="selected.data.source === 'upstream'" class="text-xs leading-5 text-white/40">{{ t('editor.imageUpstreamHint') }}</p>
            </template>
            <template v-if="selected.type === 'image_recognition'">
              <p v-if="mediaLocked('image_recognition')" class="text-xs leading-5 text-amber-200">{{ t('editor.mediaLockedHint') }}</p>
              <UFormField :label="t('editor.recognizePrompt')">
                <UTextarea v-model="selected.data.prompt" :rows="5" class="w-full" :placeholder="t('editor.recognizePlaceholder')" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.recognizeCredits') }} {{ t('editor.recognizeHint') }}</p>
            </template>
            <template v-if="selected.type === 'audio_transcription'">
              <p v-if="mediaLocked('audio_transcription')" class="text-xs leading-5 text-amber-200">{{ t('editor.mediaLockedHint') }}</p>
              <UFormField :label="t('editor.imageSource')">
                <USelect v-model="selected.data.source" :items="mediaSources" value-key="value" class="w-full" />
              </UFormField>
              <UFormField v-if="selected.data.source === 'url'" :label="t('editor.audioUrlLabel')">
                <UInput v-model="selected.data.url" class="w-full font-mono text-xs" :placeholder="t('editor.audioUrlPlaceholder')" />
              </UFormField>
              <UFormField v-if="selected.data.source === 'file'" :label="t('editor.audioFileLabel')">
                <input type="file" accept="audio/*" class="block w-full text-xs text-white/70" @change="readMediaFile">
                <p v-if="selected.data.filename" class="mt-1 text-xs text-white/50">{{ selected.data.filename }}</p>
              </UFormField>
              <UFormField :label="t('editor.audioPrompt')">
                <UTextarea v-model="selected.data.prompt" :rows="4" class="w-full" :placeholder="t('editor.audioPromptPlaceholder')" />
              </UFormField>
              <p class="text-xs leading-5 text-white/40">{{ t('editor.mediaHint') }}</p>
            </template>
            <ul v-if="selectedVariableHints.some(hint => hint.mark === 'undefined')" class="mb-0 mt-3 space-y-1 text-xs text-amber-200">
              <li v-for="hint in selectedVariableHints.filter(item => item.mark === 'undefined')" :key="hint.name">
                {{ t('editor.varUndefinedLine', { token: formatVariableToken(hint.name) }) }}
              </li>
            </ul>
          </div>
        </template>
        <div v-else>
          <p class="editor-kicker">{{ t('editor.propsKicker') }}</p>
          <h2 class="mb-2 text-lg font-extrabold text-white">{{ t('editor.noneSelected') }}</h2>
          <p class="text-sm leading-6 text-white/45">{{ t('editor.noneHint') }}</p>
          <div class="editor-cost-card">
            <p class="mb-1 text-[10px] font-extrabold uppercase tracking-[0.16em] text-white/35">{{ t('editor.maxCost') }}</p>
            <p class="mb-0 text-3xl font-extrabold text-white">{{ t('editor.maxCostValue', { cost: formatCredits(estimatedCost) }) }}</p>
            <p class="mb-0 mt-1 text-xs text-white/40">{{ t('editor.maxCostHint') }}</p>
          </div>
        </div>
        <div v-if="validationErrors.length" class="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-3">
          <h3 class="mb-2 text-sm font-extrabold text-amber-200">{{ t('editor.errors') }}</h3>
          <ul class="mb-0 list-disc space-y-1 pl-5 text-xs text-amber-100/80">
            <li v-for="err in validationErrors" :key="err">{{ err }}</li>
          </ul>
        </div>
      </aside>
    </div>
  </div>
</template>
