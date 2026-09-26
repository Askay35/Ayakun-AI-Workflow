<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'
import { useAuthAsyncData } from '~/composables/useAuthAsyncData'
import type { NodeKind, Workflow, WorkflowNode } from '~/types/api'
import { formatCredits } from '~/utils/credits'
import { slotsFromWorkflow, type ScheduleSlot } from '~/utils/schedule'
import { definedVariableNames, recordFromVariables, variablesFromRecord, type VariableRow } from '~/utils/workflow-variables'
import { MOBILE_BLOCKED_TYPES, NODE_GROUPS, NODE_META, createWorkflowNode } from '~/utils/workflow-graph'

/** Редактор мобильной цепочки: линейный список шагов вместо холста, один вход и один выход у каждого шага. */
const props = defineProps<{ workflowId: string }>()
const api = useApi()
const toast = useToast()
const { t } = useI18n()
const isMobile = useIsMobileEditor()
const id = props.workflowId
const STEP_GAP = 190

const { data: workflow } = await useAuthAsyncData<Workflow>(`workflow-${id}`, () => api.workflows.get(id))
if (!workflow.value) throw createError({ statusCode: 404, statusMessage: t('editor.notFound'), fatal: false })

const orderChain = (list: WorkflowNode[]) => {
  const byId = new Map(list.map(node => [node.id, node]))
  const seen = new Set<string>()
  const ordered: WorkflowNode[] = []
  let current: WorkflowNode | undefined = list.find(node => !node.parents.length) || list[0]
  while (current && !seen.has(current.id)) {
    ordered.push(current)
    seen.add(current.id)
    current = byId.get(current.children[0] || '')
  }
  return [...ordered, ...list.filter(node => !seen.has(node.id))]
}

const steps = ref<WorkflowNode[]>(orderChain(structuredClone(toRaw(workflow.value.draft_graph?.nodes || []))))
const workflowVariables = ref<VariableRow[]>(variablesFromRecord(workflow.value.variables))
const scheduleEnabled = ref(Boolean(workflow.value.schedule_cron || workflow.value.next_run_at))
const scheduleSlots = ref<ScheduleSlot[]>(slotsFromWorkflow(workflow.value))
const scheduleTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const scheduleActive = computed(() => scheduleEnabled.value && scheduleSlots.value.length > 0)
const workflowName = ref(workflow.value.name)
const nameDraft = ref(workflow.value.name)
const renaming = ref(false)
const saveState = ref<'saved' | 'saving' | 'dirty'>('saved')
const estimatedCost = ref(Number(workflow.value.estimated_run_cost || 0))
const validationErrors = ref<string[]>([])
const busy = ref<'publish' | 'run' | 'node' | null>(null)
useAppTitle(computed(() => workflowName.value || t('titles.editor')))

const pickerOpen = ref(false)
const insertAt = ref(0)
const settingsId = ref<string>()
const scheduleOpen = ref(false)
const varsOpen = ref(false)
const paletteQuery = ref('')

const settingsNode = computed(() => steps.value.find(node => node.id === settingsId.value))
const settingsOpen = computed({
  get: () => Boolean(settingsNode.value),
  set: (value: boolean) => { if (!value) settingsId.value = undefined }
})
const definedNames = computed(() => definedVariableNames(workflowVariables.value, steps.value))
const startsWithWebhook = computed(() => steps.value[0]?.type === 'webhook')
const soloRunBlocked = computed(() => new Set(workflow.value?.solo_run_blocked_node_types || ['if_else']))

const paletteGroups = computed(() => {
  const query = paletteQuery.value.trim().toLowerCase()
  const webhookAllowed = insertAt.value === 0 && !steps.value.some(node => node.type === 'webhook')
  return NODE_GROUPS.map(group => ({
    key: group.key,
    items: group.types
      .filter(type => !MOBILE_BLOCKED_TYPES.includes(type) && (type !== 'webhook' || webhookAllowed))
      .map(type => ({ type, ...NODE_META[type], label: t(`nodes.${type}.label`), caption: t(`nodes.${type}.caption`) }))
      .filter(item => !query || `${item.label} ${item.caption} ${item.type}`.toLowerCase().includes(query))
  })).filter(group => group.items.length)
})

const preview = (node: WorkflowNode) => {
  const data = node.data
  const text = data.query || data.prompt || data.message || data.text || data.subject || data.url || data.remote_path || data.filename || ''
  return String(text).replace(/\s+/g, ' ').trim()
}

const linkedSteps = () => steps.value.map((node, index) => ({
  ...node,
  position: { x: 0, y: index * STEP_GAP },
  parents: index > 0 ? [steps.value[index - 1]!.id] : [],
  children: index < steps.value.length - 1 ? [steps.value[index + 1]!.id] : []
}))

const saveExtras = () => ({
  schedule_slots: scheduleSlots.value.map(({ next_at: _next, ...slot }) => slot),
  schedule_enabled: scheduleActive.value,
  schedule_timezone: scheduleTimezone,
  variables: recordFromVariables(workflowVariables.value)
})

const save = async (extras: { name?: string; rotate_webhook_token?: boolean } = {}) => {
  clearTimeout(saveTimer)
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, { nodes: linkedSteps() }, { ...saveExtras(), ...extras })
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

let saveTimer: ReturnType<typeof setTimeout> | undefined
const hydrated = ref(false)
watch([steps, scheduleEnabled, scheduleSlots, workflowVariables], () => {
  if (!hydrated.value) return
  changedSincePublish.value = true
  saveState.value = 'dirty'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 900)
}, { deep: true })
onMounted(() => { hydrated.value = true })
onBeforeUnmount(() => clearTimeout(saveTimer))

const openPicker = (index: number) => {
  insertAt.value = index
  paletteQuery.value = ''
  pickerOpen.value = true
}

const addStep = (type: NodeKind) => {
  const node = createWorkflowNode(type, t(`nodes.${type}.label`), { x: 0, y: 0 })
  const next = [...steps.value]
  next.splice(insertAt.value, 0, node)
  steps.value = next
  pickerOpen.value = false
  settingsId.value = node.id
  if (type === 'webhook') void save()
}

const openSettings = (node: WorkflowNode) => { settingsId.value = node.id }
const closeSettings = () => { settingsId.value = undefined }

const removeStep = (node: WorkflowNode) => {
  if (!confirm(t('steps.deleteConfirm', { name: node.data.label || t(`nodes.${node.type}.label`) }))) return
  if (settingsId.value === node.id) settingsId.value = undefined
  steps.value = steps.value.filter(item => item.id !== node.id)
}

const startRename = () => {
  nameDraft.value = workflowName.value
  renaming.value = true
}

const commitRename = async () => {
  const next = nameDraft.value.trim()
  if (!next) {
    toast.add({ title: t('editor.nameRequired'), color: 'error' })
    return
  }
  if (next !== workflowName.value && !(await save({ name: next }))) return
  renaming.value = false
}

const rotateWebhookToken = async () => {
  if (await save({ rotate_webhook_token: true })) toast.add({ title: t('editor.webhookRotated'), color: 'success' })
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

const changedSincePublish = ref(false)
const doPublish = async () => {
  if (!(await validate())) return false
  try {
    workflow.value = await api.workflows.publish(id)
    changedSincePublish.value = false
    toast.add({ title: t('editor.published'), color: 'success' })
    return true
  } catch (error) {
    toast.add({ title: t('editor.publishError'), description: apiErrorMessage(error), color: 'error' })
    return false
  }
}

const publish = async () => {
  busy.value = 'publish'
  try {
    await doPublish()
  } finally {
    busy.value = null
  }
}

const run = async () => {
  busy.value = 'run'
  try {
    if (!(await save())) return
    // Запуск идёт по опубликованной версии, поэтому свежие правки публикуем автоматически.
    if ((workflow.value?.status !== 'published' || changedSincePublish.value) && !(await doPublish())) return
    const result = await api.workflows.run(id)
    await navigateTo(`/runs/${result.id}`)
  } catch (error) {
    toast.add({ title: t('workflows.runError'), description: apiErrorMessage(error), color: 'error' })
  } finally {
    busy.value = null
  }
}

const runStep = async (node: WorkflowNode) => {
  busy.value = 'node'
  try {
    if (!(await save())) return
    const result = await api.workflows.runNode(id, node.id)
    await navigateTo(`/runs/${result.id}`)
  } catch (error) {
    toast.add({ title: t('editor.nodeRunError'), description: apiErrorMessage(error), color: 'error' })
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <div class="steps-editor">
    <div class="steps-wrap">
      <header class="steps-head">
        <UButton to="/workflows" icon="i-lucide-arrow-left" color="neutral" variant="ghost" :aria-label="t('editor.backAria')" />
        <div class="min-w-0 flex-1">
          <p class="steps-kicker">
            <UIcon name="i-lucide-smartphone" class="size-3.5" />
            {{ t('steps.kicker') }}
          </p>
          <div v-if="renaming" class="flex items-center gap-2">
            <UInput v-model="nameDraft" autofocus maxlength="160" class="min-w-0 flex-1" @keyup.enter="commitRename" @keyup.escape="renaming = false" />
            <UButton icon="i-lucide-check" size="sm" variant="soft" :aria-label="t('editor.saveNameAria')" @click="commitRename" />
          </div>
          <button v-else type="button" class="steps-title" :title="t('editor.renameAria')" @click="startRename">
            <span class="truncate">{{ workflowName }}</span>
            <UIcon name="i-lucide-pencil" class="size-3.5 shrink-0 opacity-50" />
          </button>
          <p class="editor-save-state">
            <span class="editor-save-dot" :class="{ 'is-dirty': saveState === 'dirty', 'is-saving': saveState === 'saving' }" />
            {{ saveState === 'saving' ? t('editor.saving') : saveState === 'saved' ? t('editor.saved') : t('editor.unsaved') }}
            <span class="editor-status-badge ml-1" :class="{ 'is-published': workflow?.status === 'published' }">
              {{ workflow?.status === 'published' ? t('workflows.published') : t('workflows.draft') }}
            </span>
          </p>
        </div>
      </header>

      <div class="steps-toolbar">
        <button type="button" class="steps-chip" :class="{ 'is-on': scheduleActive }" @click="scheduleOpen = true">
          <UIcon name="i-lucide-calendar-clock" class="size-4" />
          {{ scheduleActive ? t('steps.scheduleOn', { n: scheduleSlots.length }) : t('steps.scheduleOff') }}
        </button>
        <button type="button" class="steps-chip" :class="{ 'is-on': workflowVariables.length }" @click="varsOpen = true">
          <UIcon name="i-lucide-braces" class="size-4" />
          {{ t('steps.vars', { n: workflowVariables.length }) }}
        </button>
        <span class="steps-chip is-static" :title="t('editor.maxCostHint')">
          <UIcon name="i-lucide-coins" class="size-4" />
          {{ t('editor.costUpTo', { cost: formatCredits(estimatedCost) }) }}
        </span>
      </div>

      <div v-if="!steps.length" class="steps-empty reveal">
        <span class="steps-empty-icon"><UIcon name="i-lucide-list-plus" class="size-7" /></span>
        <h2>{{ t('steps.emptyTitle') }}</h2>
        <p>{{ t('steps.emptyText') }}</p>
        <UButton :label="t('steps.addFirst')" icon="i-lucide-plus" size="xl" @click="openPicker(0)" />
      </div>

      <ol v-else class="steps-list">
        <li v-if="!startsWithWebhook" class="steps-add-top">
          <button type="button" class="steps-add-mini" @click="openPicker(0)">
            <UIcon name="i-lucide-plus" class="size-4" />
            {{ t('steps.addBefore') }}
          </button>
        </li>
        <template v-for="(node, index) in steps" :key="node.id">
          <li class="step-card reveal" :style="{ '--step-accent': NODE_META[node.type].accent, animationDelay: `${index * 40}ms` }">
            <span class="step-index">{{ index + 1 }}</span>
            <button type="button" class="step-main" @click="openSettings(node)">
              <span class="step-icon"><UIcon :name="NODE_META[node.type].icon" class="size-5" /></span>
              <span class="min-w-0 flex-1 text-left">
                <span class="step-name">{{ node.data.label || t(`nodes.${node.type}.label`) }}</span>
                <span class="step-caption">{{ t(`nodes.${node.type}.label`) }} · {{ t(`nodes.${node.type}.caption`) }}</span>
                <span v-if="preview(node)" class="step-preview">{{ preview(node) }}</span>
              </span>
            </button>
            <div class="step-actions">
              <UButton icon="i-lucide-settings-2" color="neutral" variant="soft" size="sm" :aria-label="t('steps.settings')" @click="openSettings(node)" />
              <UButton icon="i-lucide-trash-2" color="error" variant="ghost" size="sm" :aria-label="t('steps.deleteStep')" @click="removeStep(node)" />
            </div>
          </li>
          <li class="step-link">
            <span class="step-link-line" />
            <button
              v-if="index < steps.length - 1"
              type="button"
              class="step-link-add"
              :aria-label="t('steps.insertAria')"
              :title="t('steps.insertAria')"
              @click="openPicker(index + 1)"
            >
              <UIcon name="i-lucide-plus" class="size-3.5" />
            </button>
          </li>
        </template>
        <li>
          <button type="button" class="steps-add-next" @click="openPicker(steps.length)">
            <span class="steps-add-next-icon"><UIcon name="i-lucide-plus" class="size-5" /></span>
            <span>
              <span class="block font-extrabold">{{ t('steps.addAfter') }}</span>
              <span class="block text-xs muted">{{ t('steps.addAfterHint') }}</span>
            </span>
          </button>
        </li>
      </ol>

      <div v-if="validationErrors.length" class="editor-errors mt-6">
        <h3>{{ t('editor.errors') }}</h3>
        <ul>
          <li v-for="err in validationErrors" :key="err">{{ err }}</li>
        </ul>
      </div>
    </div>

    <footer class="steps-footer">
      <UButton :label="t('editor.check')" icon="i-lucide-circle-check" color="neutral" variant="ghost" class="hidden sm:inline-flex" @click="checkGraph" />
      <UButton :label="t('editor.publish')" icon="i-lucide-upload" color="neutral" variant="outline" class="flex-1 justify-center sm:flex-none" :loading="busy === 'publish'" :disabled="!steps.length" @click="publish" />
      <UButton :label="t('editor.run')" icon="i-lucide-play" class="flex-1 justify-center sm:flex-none" :loading="busy === 'run'" :disabled="!steps.length" @click="run" />
    </footer>

    <UModal v-model:open="pickerOpen" :title="t('steps.pickTitle')" :description="t('steps.pickDesc')" :fullscreen="isMobile">
      <template #body>
        <UInput v-model="paletteQuery" icon="i-lucide-search" :placeholder="t('editor.nodesSearch')" class="palette-search mb-3 w-full" />
        <div v-for="group in paletteGroups" :key="group.key" class="palette-group">
          <p class="palette-group-title">{{ t(`editor.groups.${group.key}`) }}</p>
          <button v-for="item in group.items" :key="item.type" type="button" class="palette-item" @click="addStep(item.type)">
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
        <p class="editor-hint mt-3">{{ t('steps.noBranches') }}</p>
      </template>
    </UModal>

    <UModal v-model:open="settingsOpen" :fullscreen="isMobile" :ui="{ footer: 'justify-end' }">
      <template #header>
        <div v-if="settingsNode" class="editor-node-head w-full">
          <span class="editor-node-icon" :style="{ color: NODE_META[settingsNode.type].accent, background: `${NODE_META[settingsNode.type].accent}1f` }">
            <UIcon :name="NODE_META[settingsNode.type].icon" class="size-5" />
          </span>
          <div class="min-w-0 flex-1">
            <h2 class="editor-node-name">{{ t(`nodes.${settingsNode.type}.label`) }}</h2>
            <p class="editor-node-caption">{{ t(`nodes.${settingsNode.type}.caption`) }}</p>
          </div>
        </div>
      </template>
      <template #body>
        <WorkflowNodeSettings
          v-if="settingsNode"
          :node="settingsNode"
          :defined-names="definedNames"
          :webhook-token="workflow?.webhook_token"
          @rotate-webhook="rotateWebhookToken"
        />
      </template>
      <template #footer>
        <UButton
          v-if="settingsNode && !soloRunBlocked.has(settingsNode.type)"
          :label="t('editor.runNode')"
          icon="i-lucide-play"
          color="neutral"
          variant="outline"
          :loading="busy === 'node'"
          @click="runStep(settingsNode)"
        />
        <UButton :label="t('steps.done')" icon="i-lucide-check" @click="closeSettings" />
      </template>
    </UModal>

    <UModal v-model:open="scheduleOpen" :title="t('editor.tabSchedule')" :fullscreen="isMobile">
      <template #body>
        <WorkflowSchedulePanel v-model:enabled="scheduleEnabled" v-model:slots="scheduleSlots" :timezone="scheduleTimezone" />
      </template>
    </UModal>

    <UModal v-model:open="varsOpen" :title="t('editor.tabVars')" :fullscreen="isMobile">
      <template #body>
        <WorkflowVariablesPanel v-model:items="workflowVariables" />
      </template>
    </UModal>
  </div>
</template>
