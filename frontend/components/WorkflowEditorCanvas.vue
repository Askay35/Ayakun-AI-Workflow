<script setup lang="ts">
import { ConnectionMode, MarkerType, SelectionMode, VueFlow, useVueFlow, type Connection, type Edge, type EdgeChange, type NodeChange } from '@vue-flow/core'
import { apiErrorMessage } from '~/composables/useApi'
import { useAuthAsyncData } from '~/composables/useAuthAsyncData'
import type { NodeKind, Workflow, WorkflowNode } from '~/types/api'
import { formatCredits } from '~/utils/credits'
import { slotsFromWorkflow, type ScheduleSlot } from '~/utils/schedule'
import {
  definedVariableNames,
  nodeVariableHints,
  recordFromVariables,
  variablesFromRecord,
  type VariableRow
} from '~/utils/workflow-variables'
import {
  NODE_GROUPS,
  NODE_META,
  SINGLE_INCOMING_TYPES,
  addLink,
  applyLinks,
  branchFromHandle,
  canConnect,
  createWorkflowNode,
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
const { t, tm } = useI18n()
const id = props.workflowId
const flowId = `workflow-${id}`

const { data: workflow, error: workflowError, status } = await useAuthAsyncData<Workflow>(
  `workflow-${id}`,
  () => api.workflows.get(id)
)
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

const nodeKinds = Object.keys(NODE_META) as NodeKind[]
const leftTab = ref<'nodes' | 'vars' | 'schedule'>('nodes')
const leftTabs = computed(() => [
  { key: 'nodes' as const, label: t('editor.tabNodes'), dot: false },
  { key: 'vars' as const, label: t('editor.tabVars'), dot: workflowVariables.value.length > 0 },
  { key: 'schedule' as const, label: t('editor.tabSchedule'), dot: scheduleActive.value }
])
const paletteQuery = ref('')
const paletteGroups = computed(() => {
  const query = paletteQuery.value.trim().toLowerCase()
  return NODE_GROUPS.map(group => ({
    key: group.key,
    items: group.types
      .map(type => ({
        type,
        ...NODE_META[type],
        label: t(`nodes.${type}.label`),
        caption: t(`nodes.${type}.caption`)
      }))
      .filter(item => !query || `${item.label} ${item.caption} ${item.type}`.toLowerCase().includes(query))
  })).filter(group => group.items.length)
})
const editorTips = computed(() => tm<string[]>('editor.tips'))
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
const definedNames = computed(() => definedVariableNames(workflowVariables.value, nodes.value))
const hintsFor = (nodeId: string) => {
  const node = nodes.value.find(item => item.id === nodeId)
  return node ? nodeVariableHints(node, definedNames.value) : []
}
const defaultEdgeOptions = {
  type: 'workflow',
  markerEnd: MarkerType.ArrowClosed,
  style: { stroke: '#a99cff', strokeWidth: 2 },
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
  const node = createWorkflowNode(type, t(`nodes.${type}.label`), position)
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
      <div class="flex min-w-0 items-center gap-2">
        <UButton to="/workflows" icon="i-lucide-arrow-left" color="neutral" variant="ghost" :aria-label="t('editor.backAria')" />
        <div class="min-w-0">
          <div v-if="renaming" class="flex min-w-0 items-center gap-2">
            <UInput
              v-model="nameDraft"
              autofocus
              class="min-w-0 w-[min(320px,46vw)]"
              maxlength="160"
              @keyup.enter="commitRename"
              @keyup.escape="cancelRename"
            />
            <UButton icon="i-lucide-check" size="sm" color="primary" variant="soft" :aria-label="t('editor.saveNameAria')" @click="commitRename" />
            <UButton icon="i-lucide-x" size="sm" color="neutral" variant="ghost" :aria-label="t('editor.cancelAria')" @click="cancelRename" />
          </div>
          <button
            v-else
            type="button"
            class="group flex max-w-full items-center gap-2 text-left"
            :title="t('editor.renameAria')"
            @click="startRename"
          >
            <h1 class="editor-title">{{ workflowName }}</h1>
            <span class="editor-status-badge" :class="{ 'is-published': workflow?.status === 'published' }">
              {{ workflow?.status === 'published' ? t('workflows.published') : t('workflows.draft') }}
            </span>
            <UIcon name="i-lucide-pencil" class="size-3.5 shrink-0 text-[#9a9fba] transition group-hover:text-[#6d4aff]" />
          </button>
          <p class="editor-save-state">
            <span class="editor-save-dot" :class="{ 'is-dirty': saveState === 'dirty', 'is-saving': saveState === 'saving' }" />
            {{ saveState === 'saving' ? t('editor.saving') : saveState === 'saved' ? t('editor.saved') : t('editor.unsaved') }}
          </p>
        </div>
      </div>
      <div class="flex flex-wrap items-center justify-end gap-2">
        <span class="editor-cost" :title="t('editor.maxCostHint')"><UIcon name="i-lucide-coins" class="size-3.5" />{{ t('editor.costUpTo', { cost: formatCredits(estimatedCost) }) }}</span>
        <UButton :label="t('editor.check')" icon="i-lucide-circle-check" color="neutral" variant="ghost" @click="checkGraph" />
        <UButton :label="t('editor.publish')" icon="i-lucide-upload" color="neutral" variant="outline" @click="publish" />
        <UButton :label="t('editor.run')" icon="i-lucide-play" @click="run" />
      </div>
    </header>
    <div class="editor-body">
      <aside class="editor-pane editor-pane-left">
        <div class="editor-tabs" role="tablist">
          <button
            v-for="tab in leftTabs"
            :key="tab.key"
            type="button"
            role="tab"
            class="editor-tab"
            :class="{ 'is-active': leftTab === tab.key }"
            :aria-selected="leftTab === tab.key"
            @click="leftTab = tab.key"
          >
            {{ tab.label }}
            <span v-if="tab.dot" class="editor-tab-dot" />
          </button>
        </div>
        <div v-show="leftTab === 'nodes'" class="editor-tab-panel">
          <UInput
            v-model="paletteQuery"
            icon="i-lucide-search"
            :placeholder="t('editor.nodesSearch')"
            class="palette-search w-full"
          />
          <div v-for="group in paletteGroups" :key="group.key" class="palette-group" role="list">
            <p class="palette-group-title">{{ t(`editor.groups.${group.key}`) }}</p>
            <button
              v-for="item in group.items"
              :key="item.type"
              type="button"
              :draggable="true"
              class="palette-item"
              role="listitem"
              :title="t('editor.nodesHint')"
              @dragstart="onDragStart($event, item.type)"
              @click="addFromPalette(item.type)"
            >
              <span class="palette-icon" :style="{ color: item.accent, background: `${item.accent}1f` }">
                <UIcon :name="item.icon" class="size-4" />
              </span>
              <span class="min-w-0 text-left">
                <span class="palette-name">{{ item.label }}</span>
                <span class="palette-caption">{{ item.caption }}</span>
              </span>
              <UIcon name="i-lucide-plus" class="palette-add size-4" />
            </button>
          </div>
          <p v-if="!paletteGroups.length" class="palette-empty">{{ t('editor.nodesNotFound') }}</p>
        </div>
        <div v-show="leftTab === 'vars'" class="editor-tab-panel">
          <WorkflowVariablesPanel v-model:items="workflowVariables" />
        </div>
        <div v-show="leftTab === 'schedule'" class="editor-tab-panel">
          <WorkflowSchedulePanel
            v-model:enabled="scheduleEnabled"
            v-model:slots="scheduleSlots"
            :timezone="scheduleTimezone"
          />
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
            <template v-for="kind in nodeKinds" #[`node-${kind}`]="{ id: nodeId, data, selected: active }">
              <WorkflowNodeCard :node-id="nodeId" :kind="kind" :data="data" :selected="active" :hints="hintsFor(nodeId)" />
            </template>
          </VueFlow>
          <template #fallback>
            <div class="grid h-full place-items-center text-sm text-[#6b7090]">{{ t('editor.loading') }}</div>
          </template>
        </ClientOnly>
        <div v-if="!nodes.length" class="editor-empty">
          <span class="editor-empty-icon"><UIcon name="i-lucide-workflow" class="size-6" /></span>
          <p class="mb-1 text-base font-extrabold text-[var(--ink)]">{{ t('editor.emptyTitle') }}</p>
          <p class="mb-0 max-w-xs text-center text-sm leading-6 text-[#6b7090]">{{ t('editor.emptyText') }}</p>
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
          <h2 class="editor-node-name mb-2">{{ t('editor.edgeTitle') }}</h2>
          <p class="editor-hint">{{ t('editor.edgeHint') }}</p>
          <UButton class="mt-4" :label="t('editor.deleteEdge')" icon="i-lucide-unlink" color="error" variant="soft" @click="unlinkSelectedEdge" />
        </template>
        <template v-else-if="selected">
          <div class="editor-node-head">
            <span class="editor-node-icon" :style="{ color: NODE_META[selected.type].accent, background: `${NODE_META[selected.type].accent}1f` }">
              <UIcon :name="NODE_META[selected.type].icon" class="size-5" />
            </span>
            <div class="min-w-0 flex-1">
              <h2 class="editor-node-name">{{ t(`nodes.${selected.type}.label`) }}</h2>
              <p class="editor-node-caption">{{ t(`nodes.${selected.type}.caption`) }}</p>
            </div>
            <div class="flex items-center gap-1">
              <UButton
                v-if="canSoloRunSelected"
                icon="i-lucide-play"
                :label="t('editor.runNode')"
                size="sm"
                variant="soft"
                :loading="nodeRunLoading"
                @click="runSelectedNode"
              />
              <UButton icon="i-lucide-trash-2" color="error" variant="ghost" size="sm" :aria-label="t('editor.deleteNode')" @click="deleteSelected" />
            </div>
          </div>
          <WorkflowNodeSettings
            class="mt-4"
            :node="selected"
            :defined-names="definedNames"
            :webhook-token="workflow?.webhook_token"
            @rotate-webhook="rotateWebhookToken"
          />
        </template>
        <div v-else>
          <p class="editor-kicker">{{ t('editor.propsKicker') }}</p>
          <h2 class="editor-node-name mb-2">{{ t('editor.noneSelected') }}</h2>
          <p class="editor-hint">{{ t('editor.noneHint') }}</p>
          <div class="editor-cost-card">
            <p class="editor-kicker">{{ t('editor.maxCost') }}</p>
            <p class="mb-0 text-3xl font-extrabold tracking-tight text-[var(--ink)]">{{ t('editor.maxCostValue', { cost: formatCredits(estimatedCost) }) }}</p>
            <p class="editor-hint mt-1">{{ t('editor.maxCostHint') }}</p>
          </div>
          <div class="mt-5 grid gap-2">
            <p class="editor-kicker">{{ t('editor.tipsTitle') }}</p>
            <p v-for="tip in editorTips" :key="tip" class="editor-hint flex gap-2">
              <UIcon name="i-lucide-lightbulb" class="mt-0.5 size-3.5 shrink-0 text-[#6d4aff]" />
              <span>{{ tip }}</span>
            </p>
          </div>
        </div>
        <div v-if="validationErrors.length" class="editor-errors">
          <h3>{{ t('editor.errors') }}</h3>
          <ul>
            <li v-for="err in validationErrors" :key="err">{{ err }}</li>
          </ul>
        </div>
      </aside>
    </div>
  </div>
</template>
