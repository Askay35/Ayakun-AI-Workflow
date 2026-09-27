<script setup lang="ts">
import type { SearchPeriod, WorkflowNode } from '~/types/api'
import { maxOutputTokensFromCredits, promptMaxCredits } from '~/utils/prompt-max-cost'
import { nodeVariableHints } from '~/utils/workflow-variables'
import { joinCondition, splitCondition } from '~/utils/condition'
import { IF_ELSE_CONDITION_PLACEHOLDER, TELEGRAM_MESSAGE_PLACEHOLDER } from '~/utils/workflow-graph'

/** Поля настроек узла: общие для холста и мобильного списка шагов. Правит node.data напрямую. */
const props = defineProps<{
  node: WorkflowNode
  definedNames: Set<string>
  webhookToken?: string | null
}>()
const emit = defineEmits<{ 'rotate-webhook': [] }>()
const toast = useToast()
const { t } = useI18n()
const selected = computed(() => props.node)

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
watch(() => props.node.id, () => {
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
  const max = selected.value.type === 'audio_transcription'
    ? 6 * 1024 * 1024
    : selected.value.type === 'file' ? 10 * 1024 * 1024 : 30 * 1024 * 1024
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
  { label: t('editor.transformMap'), value: 'map' },
  { label: t('editor.transformMerge'), value: 'merge' }
])
const trelloOperations = computed(() => ['create_card', 'list_cards', 'move_card', 'add_comment'].map(value => ({ label: t(`trelloOps.${value}`), value })))
const jiraOperations = computed(() => ['create_issue', 'search', 'add_comment'].map(value => ({ label: t(`jiraOps.${value}`), value })))
const excelOperations = computed(() => ['read', 'append', 'update'].map(value => ({ label: t(`excelOps.${value}`), value })))
const bitrix24Entities = computed(() => ['lead', 'deal', 'contact', 'company'].map(value => ({ label: t(`bitrix24Entities.${value}`), value })))
const bitrix24Operations = computed(() => ['create', 'update', 'get', 'list', 'delete'].map(value => ({ label: t(`bitrix24Ops.${value}`), value })))
const spreadsheetOperations = computed(() => [
  { label: t('editor.spreadsheetRead'), value: 'read' },
  { label: t('editor.spreadsheetWrite'), value: 'write' }
])
const spreadsheetFormats = computed(() => [
  { label: t('editor.formatAuto'), value: 'auto' },
  { label: 'CSV', value: 'csv' },
  { label: 'XLSX', value: 'xlsx' }
])
const linkedinVisibility = computed(() => [
  { label: t('editor.linkedinPublic'), value: 'PUBLIC' },
  { label: t('editor.linkedinConnections'), value: 'CONNECTIONS' }
])
const sortDirections = computed(() => [
  { label: t('editor.sortAsc'), value: 'asc' },
  { label: t('editor.sortDesc'), value: 'desc' }
])
const runtimeConfig = useRuntimeConfig()
const webhookUrl = computed(() => {
  const token = props.webhookToken
  if (!token) return ''
  return `${String(runtimeConfig.public.siteUrl)}${String(runtimeConfig.public.apiBase).replace(/\/$/, '')}/webhooks/${token}`
})
const copyWebhookUrl = async () => {
  if (!webhookUrl.value) return
  await navigator.clipboard.writeText(webhookUrl.value)
  toast.add({ title: t('editor.urlCopied'), color: 'success' })
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
const loopVariableOptions = computed(() =>
  [...props.definedNames].sort().map(name => ({ label: name, value: name }))
)
const selectedVariableHints = computed(() => selected.value ? nodeVariableHints(selected.value, props.definedNames) : [])
const rotateWebhookToken = () => emit('rotate-webhook')
</script>

<template>
  <div class="space-y-4">
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
      <p class="editor-hint">{{ t('editor.promptHint', { example: VARIABLE_NAME_EXAMPLE }) }}</p>
      <UFormField :label="t('editor.maxRunCost')">
        <UInput v-model="selectedMaxRunCredits" type="number" min="1" step="1" class="w-full" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.maxRunCostHint') }}</p>
      <WorkflowVariableAssignments v-model:items="selectedAssignments" />
    </template>
    <template v-if="selected.type === 'http_request'">
      <UFormField :label="t('editor.requestJson')">
        <UTextarea v-model="selectedRequestJson" :rows="14" class="w-full font-mono text-xs" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.httpHint', { json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE }) }}</p>
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
      <p v-if="conditionUnparsed" class="editor-warn">{{ t('editor.conditionRaw') }}</p>
      <p class="editor-hint">{{ t('editor.ifHint', { compare: VARIABLE_COMPARE_EXAMPLE, placeholder: IF_ELSE_CONDITION_PLACEHOLDER }) }}</p>
      <details class="editor-help">
        <summary>{{ t('editor.ifHelpTitle') }}</summary>
        <div class="editor-help-body">
          <p class="mb-1">{{ t('editor.ifHelpCompare', { example: JSON_EXPRESSION_EXAMPLE }) }}</p>
          <p class="mb-1">{{ t('editor.ifHelpOps') }}</p>
          <p class="mb-1">{{ t('editor.ifHelpLits') }}</p>
          <p class="mb-1">{{ t('editor.ifHelpMissing') }}</p>
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
      <p class="editor-hint">{{ t('editor.telegramHint', { root: ROOT_JSON_EXAMPLE, json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE, loop: TELEGRAM_LOOP_EXAMPLE }) }}</p>
    </template>
    <template v-if="selected.type === 'webhook'">
      <p class="editor-hint">{{ t('editor.webhookIntro', { body: WEBHOOK_BODY_EXAMPLE }) }}</p>
      <UFormField :label="t('editor.webhookUrl')">
        <UInput :model-value="webhookUrl" readonly class="w-full font-mono text-xs" :placeholder="t('editor.webhookUrlPlaceholder')" />
      </UFormField>
      <div class="flex flex-wrap gap-2">
        <UButton :label="t('editor.copy')" icon="i-lucide-copy" color="neutral" variant="outline" :disabled="!webhookUrl" @click="copyWebhookUrl" />
        <UButton :label="t('editor.newKey')" icon="i-lucide-refresh-cw" color="neutral" variant="ghost" :disabled="!webhookUrl" @click="rotateWebhookToken" />
      </div>
      <p class="editor-hint">{{ t('editor.webhookAfter') }}</p>
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
      <p class="editor-hint">{{ t('editor.sheetsHint', { json: JSON_EXPRESSION_EXAMPLE }) }}</p>
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
      <p class="editor-hint">{{ t('editor.emailHint', { root: ROOT_JSON_EXAMPLE, json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE, loop: TELEGRAM_LOOP_EXAMPLE }) }}</p>
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
      <UFormField v-if="selected.data.operation === 'rename' || selected.data.operation === 'set' || selected.data.operation === 'map' || selected.data.operation === 'merge'" :label="selected.data.operation === 'map' ? t('editor.mapTemplate') : selected.data.operation === 'merge' ? t('editor.mergeExtra') : t('editor.fieldMap')">
        <UTextarea
          v-model="selected.data.mapping_json"
          :rows="8"
          class="w-full font-mono text-xs"
          :placeholder="selected.data.operation === 'rename' ? TRANSFORM_RENAME_PLACEHOLDER : selected.data.operation === 'set' || selected.data.operation === 'merge' ? TRANSFORM_SET_PLACEHOLDER : TRANSFORM_MAP_PLACEHOLDER"
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
      <p class="editor-hint">{{ selected.data.operation === 'merge' ? t('editor.mergeHint') : t('editor.transformHint') }}</p>
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
      <p class="editor-hint">{{ t('editor.sqlHint', { json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE }) }}</p>
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
          <p v-else class="editor-hint">{{ t('editor.loopNoVars') }}</p>
        </UFormField>
        <UFormField :label="t('editor.conditionOp')">
          <USelect v-model="selected.data.while_operator" :items="conditionOperators" value-key="value" class="w-full" />
        </UFormField>
        <UFormField :label="t('editor.loopValue')">
          <UInput v-model="selected.data.while_value" class="w-full font-mono text-xs" placeholder="0" />
        </UFormField>
      </template>
      <p class="editor-hint">{{ t('editor.loopHint') }}</p>
    </template>
    <template v-if="selected.type === 'delay'">
      <UFormField :label="t('editor.delayAmount')">
        <UInput v-model="selected.data.amount" class="w-full font-mono text-xs" placeholder="0.35" />
      </UFormField>
      <UFormField :label="t('editor.delayUnit')">
        <USelect v-model="selected.data.unit" :items="delayUnits" value-key="value" class="w-full" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.delayHint') }}</p>
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
      <UFormField v-if="selected.data.operation === 'upload'" :label="t('editor.yandexContent')">
        <UTextarea v-model="selected.data.content" :rows="4" class="w-full font-mono text-xs" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.yandexHint') }}</p>
    </template>
    <template v-if="selected.type === 'image_generation'">
      <UFormField :label="t('editor.imagePrompt')">
        <UTextarea v-model="selected.data.prompt" :rows="6" class="w-full" :placeholder="t('editor.imagePromptPlaceholder')" />
      </UFormField>
    </template>
    <template v-if="selected.type === 'image'">
      <UFormField :label="t('editor.imageSource')">
        <USelect v-model="selected.data.source" :items="mediaSources" value-key="value" class="w-full" />
      </UFormField>
      <UFormField v-if="selected.data.source === 'url'" :label="t('editor.imageUrlLabel')">
        <UInput v-model="selected.data.url" class="w-full font-mono text-xs" :placeholder="t('editor.imageUrlPlaceholder')" />
      </UFormField>
      <UFormField v-if="selected.data.source === 'file'" :label="t('editor.imageFileLabel')">
        <input type="file" accept="image/*" class="block w-full" @change="readMediaFile">
        <p v-if="selected.data.filename" class="editor-hint mt-1">{{ selected.data.filename }}</p>
      </UFormField>
      <p v-if="selected.data.source === 'upstream'" class="editor-hint">{{ t('editor.imageUpstreamHint') }}</p>
    </template>
    <template v-if="selected.type === 'image_recognition'">
      <UFormField :label="t('editor.recognizePrompt')">
        <UTextarea v-model="selected.data.prompt" :rows="5" class="w-full" :placeholder="t('editor.recognizePlaceholder')" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.recognizeHint') }}</p>
    </template>
    <template v-if="selected.type === 'audio_transcription'">
      <UFormField :label="t('editor.imageSource')">
        <USelect v-model="selected.data.source" :items="mediaSources" value-key="value" class="w-full" />
      </UFormField>
      <UFormField v-if="selected.data.source === 'url'" :label="t('editor.audioUrlLabel')">
        <UInput v-model="selected.data.url" class="w-full font-mono text-xs" :placeholder="t('editor.audioUrlPlaceholder')" />
      </UFormField>
      <UFormField v-if="selected.data.source === 'file'" :label="t('editor.audioFileLabel')">
        <input type="file" accept="audio/*" class="block w-full" @change="readMediaFile">
        <p v-if="selected.data.filename" class="editor-hint mt-1">{{ selected.data.filename }}</p>
      </UFormField>
      <UFormField :label="t('editor.audioPrompt')">
        <UTextarea v-model="selected.data.prompt" :rows="4" class="w-full" :placeholder="t('editor.audioPromptPlaceholder')" />
      </UFormField>
    </template>
    <template v-if="selected.type === 'slack'">
      <UFormField :label="t('editor.slackWebhook')">
        <UInput v-model="selected.data.webhook_url" type="password" autocomplete="new-password" class="w-full font-mono text-xs" placeholder="https://hooks.slack.com/services/…" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.slackOr') }}</p>
      <UFormField :label="t('editor.botToken')">
        <UInput v-model="selected.data.bot_token" type="password" autocomplete="new-password" class="w-full font-mono text-xs" placeholder="xoxb-…" />
      </UFormField>
      <UFormField :label="t('editor.slackChannel')">
        <UInput v-model="selected.data.channel" class="w-full font-mono text-xs" placeholder="#general" />
      </UFormField>
      <UFormField :label="t('editor.messageText')">
        <UTextarea v-model="selected.data.message" :rows="6" class="w-full font-mono text-xs" :placeholder="TELEGRAM_MESSAGE_PLACEHOLDER" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.slackHint', { json: JSON_EXPRESSION_EXAMPLE, variable: VARIABLE_NAME_EXAMPLE }) }}</p>
    </template>
    <template v-if="selected.type === 'trello'">
      <UFormField :label="t('editor.operation')">
        <USelect v-model="selected.data.operation" :items="trelloOperations" value-key="value" class="w-full" />
      </UFormField>
      <div class="grid grid-cols-2 gap-2">
        <UFormField :label="t('editor.apiKey')">
          <UInput v-model="selected.data.api_key" type="password" autocomplete="new-password" class="w-full" />
        </UFormField>
        <UFormField :label="t('editor.trelloToken')">
          <UInput v-model="selected.data.token" type="password" autocomplete="new-password" class="w-full" />
        </UFormField>
      </div>
      <UFormField v-if="selected.data.operation !== 'add_comment'" :label="selected.data.operation === 'move_card' ? t('editor.trelloTargetList') : t('editor.trelloList')">
        <UInput v-model="selected.data.list_id" class="w-full font-mono text-xs" placeholder="64f1c0…" />
      </UFormField>
      <UFormField v-if="selected.data.operation === 'move_card' || selected.data.operation === 'add_comment'" :label="t('editor.trelloCard')">
        <UInput v-model="selected.data.card_id" class="w-full font-mono text-xs" :placeholder="JSON_EXPRESSION_EXAMPLE" />
      </UFormField>
      <UFormField v-if="selected.data.operation === 'create_card'" :label="t('editor.trelloName')">
        <UInput v-model="selected.data.name" class="w-full" :placeholder="t('editor.trelloNamePlaceholder')" />
      </UFormField>
      <UFormField v-if="selected.data.operation === 'create_card' || selected.data.operation === 'add_comment'" :label="selected.data.operation === 'add_comment' ? t('editor.comment') : t('editor.description')">
        <UTextarea v-model="selected.data.description" :rows="5" class="w-full font-mono text-xs" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.trelloHint') }}</p>
      <WorkflowVariableAssignments v-model:items="selectedAssignments" />
    </template>
    <template v-if="selected.type === 'jira'">
      <UFormField :label="t('editor.operation')">
        <USelect v-model="selected.data.operation" :items="jiraOperations" value-key="value" class="w-full" />
      </UFormField>
      <UFormField :label="t('editor.jiraUrl')">
        <UInput v-model="selected.data.base_url" class="w-full font-mono text-xs" placeholder="https://company.atlassian.net" />
      </UFormField>
      <div class="grid grid-cols-2 gap-2">
        <UFormField label="Email">
          <UInput v-model="selected.data.email" class="w-full" placeholder="you@company.com" />
        </UFormField>
        <UFormField :label="t('editor.apiToken')">
          <UInput v-model="selected.data.api_token" type="password" autocomplete="new-password" class="w-full" />
        </UFormField>
      </div>
      <template v-if="selected.data.operation === 'create_issue'">
        <div class="grid grid-cols-2 gap-2">
          <UFormField :label="t('editor.jiraProject')">
            <UInput v-model="selected.data.project_key" class="w-full font-mono text-xs" placeholder="OPS" />
          </UFormField>
          <UFormField :label="t('editor.jiraIssueType')">
            <UInput v-model="selected.data.issue_type" class="w-full" placeholder="Task" />
          </UFormField>
        </div>
        <UFormField :label="t('editor.jiraSummary')">
          <UInput v-model="selected.data.summary" class="w-full" />
        </UFormField>
        <UFormField :label="t('editor.description')">
          <UTextarea v-model="selected.data.description" :rows="5" class="w-full font-mono text-xs" />
        </UFormField>
      </template>
      <UFormField v-if="selected.data.operation === 'search'" label="JQL">
        <UTextarea v-model="selected.data.jql" :rows="3" class="w-full font-mono text-xs" placeholder="project = OPS AND status != Done ORDER BY created DESC" />
      </UFormField>
      <template v-if="selected.data.operation === 'add_comment'">
        <UFormField :label="t('editor.jiraIssueKey')">
          <UInput v-model="selected.data.issue_key" class="w-full font-mono text-xs" placeholder="OPS-123" />
        </UFormField>
        <UFormField :label="t('editor.comment')">
          <UTextarea v-model="selected.data.comment" :rows="5" class="w-full font-mono text-xs" />
        </UFormField>
      </template>
      <p class="editor-hint">{{ t('editor.jiraHint') }}</p>
      <WorkflowVariableAssignments v-model:items="selectedAssignments" />
    </template>
    <template v-if="selected.type === 'bitrix24'">
      <div class="grid grid-cols-2 gap-2">
        <UFormField :label="t('editor.bitrix24Entity')">
          <USelect v-model="selected.data.entity" :items="bitrix24Entities" value-key="value" class="w-full" />
        </UFormField>
        <UFormField :label="t('editor.operation')">
          <USelect v-model="selected.data.operation" :items="bitrix24Operations" value-key="value" class="w-full" />
        </UFormField>
      </div>
      <UFormField :label="t('editor.bitrix24Webhook')">
        <UInput v-model="selected.data.webhook_url" type="password" autocomplete="new-password" class="w-full font-mono text-xs" placeholder="https://портал.bitrix24.ru/rest/1/xxxxxxxxxxxxxxxx/" />
      </UFormField>
      <UFormField v-if="selected.data.operation !== 'create' && selected.data.operation !== 'list'" :label="t('editor.bitrix24ItemId')">
        <UInput v-model="selected.data.item_id" class="w-full font-mono text-xs" :placeholder="JSON_EXPRESSION_EXAMPLE" />
      </UFormField>
      <UFormField v-if="selected.data.operation === 'create' || selected.data.operation === 'update'" :label="t('editor.bitrix24Fields')">
        <UTextarea v-model="selected.data.fields_json" :rows="6" class="w-full font-mono text-xs" placeholder='{ "TITLE": "{{$body.name}}" }' />
      </UFormField>
      <UFormField v-if="selected.data.operation === 'list'" :label="t('editor.bitrix24Filter')">
        <UTextarea v-model="selected.data.filter_json" :rows="4" class="w-full font-mono text-xs" placeholder='{ "STAGE_ID": "NEW" }' />
      </UFormField>
      <p class="editor-hint">{{ t('editor.bitrix24Hint') }}</p>
      <WorkflowVariableAssignments v-model:items="selectedAssignments" />
    </template>
    <template v-if="selected.type === 'excel'">
      <UFormField :label="t('editor.action')">
        <USelect v-model="selected.data.operation" :items="excelOperations" value-key="value" class="w-full" />
      </UFormField>
      <UFormField :label="t('editor.excelToken')">
        <UInput v-model="selected.data.access_token" type="password" autocomplete="new-password" class="w-full" placeholder="eyJ0eXAi…" />
      </UFormField>
      <UFormField :label="t('editor.excelPath')">
        <UInput v-model="selected.data.file_path" class="w-full font-mono text-xs" placeholder="/Отчёты/sales.xlsx" />
      </UFormField>
      <div class="grid grid-cols-2 gap-2">
        <UFormField :label="t('editor.excelSheet')">
          <UInput v-model="selected.data.worksheet" class="w-full font-mono text-xs" placeholder="Sheet1" />
        </UFormField>
        <UFormField v-if="selected.data.operation === 'append'" :label="t('editor.excelTable')">
          <UInput v-model="selected.data.table" class="w-full font-mono text-xs" placeholder="Table1" />
        </UFormField>
        <UFormField v-else :label="t('editor.excelRange')">
          <UInput v-model="selected.data.cell_range" class="w-full font-mono text-xs" placeholder="A1:D50" />
        </UFormField>
      </div>
      <UFormField v-if="selected.data.operation !== 'read'" :label="t('editor.rowValues')">
        <UTextarea v-model="selected.data.values_json" :rows="6" class="w-full font-mono text-xs" placeholder='[["Ada", 3]] / [{"name":"Ada","score":3}]' />
      </UFormField>
      <p class="editor-hint">{{ t('editor.excelHint') }}</p>
      <WorkflowVariableAssignments v-model:items="selectedAssignments" />
    </template>
    <template v-if="selected.type === 'file'">
      <UFormField :label="t('editor.fileLabel')">
        <input type="file" class="block w-full" @change="readMediaFile">
        <p v-if="selected.data.filename" class="editor-hint mt-1">{{ selected.data.filename }}</p>
      </UFormField>
      <p class="editor-hint">{{ t('editor.fileHint') }}</p>
    </template>
    <template v-if="selected.type === 'spreadsheet'">
      <UFormField :label="t('editor.operation')">
        <USelect v-model="selected.data.operation" :items="spreadsheetOperations" value-key="value" class="w-full" />
      </UFormField>
      <UFormField :label="t('editor.fileFormat')">
        <USelect v-model="selected.data.file_format" :items="spreadsheetFormats" value-key="value" class="w-full" />
      </UFormField>
      <div class="grid grid-cols-2 gap-2">
        <UFormField :label="t('editor.excelSheet')">
          <UInput v-model="selected.data.sheet" class="w-full font-mono text-xs" placeholder="Sheet1" />
        </UFormField>
        <UFormField :label="t('editor.delimiter')">
          <UInput v-model="selected.data.delimiter" class="w-full font-mono text-xs" :placeholder="t('editor.delimiterAuto')" maxlength="1" />
        </UFormField>
      </div>
      <label class="flex items-center gap-2 text-[13px] font-semibold">
        <UCheckbox v-model="selected.data.header_row" />
        {{ t('editor.headerRow') }}
      </label>
      <template v-if="selected.data.operation === 'write'">
        <UFormField :label="t('editor.dataPath')">
          <UInput v-model="selected.data.path" class="w-full font-mono text-xs" :placeholder="t('editor.dataPathPlaceholder')" />
        </UFormField>
        <UFormField :label="t('editor.fileName')">
          <UInput v-model="selected.data.filename" class="w-full font-mono text-xs" placeholder="report-{{date}}.xlsx" />
        </UFormField>
      </template>
      <p class="editor-hint">{{ selected.data.operation === 'write' ? t('editor.spreadsheetWriteHint') : t('editor.spreadsheetReadHint') }}</p>
      <WorkflowVariableAssignments v-model:items="selectedAssignments" />
    </template>
    <template v-if="selected.type === 'linkedin'">
      <UFormField :label="t('editor.linkedinToken')">
        <UInput v-model="selected.data.access_token" type="password" autocomplete="new-password" class="w-full" />
      </UFormField>
      <UFormField :label="t('editor.linkedinAuthor')">
        <UInput v-model="selected.data.author" class="w-full font-mono text-xs" placeholder="urn:li:person:AbC123 / urn:li:organization:12345" />
      </UFormField>
      <UFormField :label="t('editor.linkedinVisibility')">
        <USelect v-model="selected.data.visibility" :items="linkedinVisibility" value-key="value" class="w-full" />
      </UFormField>
      <UFormField :label="t('editor.linkedinText')">
        <UTextarea v-model="selected.data.text" :rows="7" class="w-full" :placeholder="t('editor.linkedinTextPlaceholder')" />
      </UFormField>
      <p class="editor-hint">{{ t('editor.linkedinHint') }}</p>
    </template>
    <ul v-if="selectedVariableHints.some(hint => hint.mark === 'undefined')" class="editor-warn list-none space-y-1">
      <li v-for="hint in selectedVariableHints.filter(item => item.mark === 'undefined')" :key="hint.name">
        {{ t('editor.varUndefinedLine', { token: formatVariableToken(hint.name) }) }}
      </li>
    </ul>
  </div>
</template>
