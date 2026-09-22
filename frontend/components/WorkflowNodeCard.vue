<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { NodeKind, WorkflowNode } from '~/types/api'
import type { VariableHint } from '~/utils/workflow-variables'
import { NODE_META } from '~/utils/workflow-graph'

const props = defineProps<{
  nodeId: string
  kind: NodeKind
  data: WorkflowNode['data']
  selected?: boolean
  hints?: VariableHint[]
}>()

const { t } = useI18n()
const meta = computed(() => NODE_META[props.kind])
const label = computed(() => props.data.label || t(`nodes.${props.kind}.label`))
const caption = computed(() => t(`nodes.${props.kind}.caption`))
const preview = computed(() => {
  if (props.kind === 'web_search') return props.data.query?.trim() || t('nodePreview.queryEmpty')
  if (props.kind === 'prompt') return props.data.prompt?.trim() || t('nodePreview.promptEmpty')
  if (props.kind === 'http_request') return props.data.request_json?.trim() || t('nodePreview.httpEmpty')
  if (props.kind === 'if_else') return props.data.condition?.trim() || t('nodePreview.conditionEmpty')
  if (props.kind === 'telegram_send') {
    const text = props.data.message?.trim()
    if (text) return text
    return props.data.chat_id ? t('nodePreview.telegramChat', { id: props.data.chat_id }) : t('nodePreview.telegramYou')
  }
  if (props.kind === 'webhook') return t('nodePreview.webhook')
  if (props.kind === 'google_sheets') {
    const operation = props.data.operation === 'append'
      ? t('nodePreview.sheetsAppend')
      : props.data.operation === 'update'
        ? t('nodePreview.sheetsUpdate')
        : t('nodePreview.sheetsRead')
    return props.data.spreadsheet_id?.trim() ? `${operation} · ${props.data.spreadsheet_id}` : operation
  }
  if (props.kind === 'email') {
    return props.data.to?.trim() ? t('nodePreview.emailTo', { to: props.data.to }) : t('nodePreview.emailSend')
  }
  if (props.kind === 'data_transform') {
    return t(`transformOps.${props.data.operation || 'select'}`) || t('nodePreview.transform')
  }
  if (props.kind === 'sql_query') return props.data.query?.trim() || t('nodePreview.sqlEmpty')
  if (props.kind === 'loop') {
    if (props.data.mode === 'times') return props.data.times?.trim() || t('nodePreview.loopTimes')
    if (props.data.mode === 'while') return props.data.while_variable?.trim() || t('nodePreview.loopWhile')
    return props.data.source?.trim() || t('nodePreview.loopEach')
  }
  if (props.kind === 'delay') {
    const amount = props.data.amount?.trim()
    return amount ? `${amount} ${props.data.unit === 'minutes' ? t('nodePreview.delayMinutes') : t('nodePreview.delaySeconds')}` : t('nodePreview.delayEmpty')
  }
  if (props.kind === 'yandex_disk') return props.data.remote_path?.trim() || t('nodePreview.yandexEmpty')
  if (props.kind === 'image_generation') return props.data.prompt?.trim() || t('nodePreview.imagePromptEmpty')
  if (props.kind === 'image') return props.data.url?.trim() || props.data.filename?.trim() || t('nodePreview.imageEmpty')
  if (props.kind === 'image_recognition') return props.data.prompt?.trim() || t('nodePreview.recognizeEmpty')
  if (props.kind === 'audio_transcription') return props.data.url?.trim() || props.data.filename?.trim() || t('nodePreview.audioEmpty')
  return label.value
})
const hintTitle = (mark: VariableHint['mark']) => (
  mark === 'undefined' ? t('nodePreview.hintUndefined') : mark === 'write' ? t('nodePreview.hintWrite') : t('nodePreview.hintRead')
)
</script>

<template>
  <div class="n8n-node" :class="[`is-${kind}`, { active: selected }]">
    <Handle
      v-if="kind !== 'webhook'"
      :id="`${nodeId}-in`"
      type="target"
      :position="Position.Left"
      class="n8n-handle n8n-handle-in"
    />
    <div class="top-node-bar" :style="{ background: meta.accent }" />
    <div class="n8n-node-body">
      <div class="n8n-node-head">
        <span class="n8n-node-icon" :style="{ background: `${meta.accent}22`, color: meta.accent }">
          <UIcon :name="meta.icon" class="size-4" />
        </span>
        <div class="min-w-0">
          <strong class="n8n-node-title">{{ label }}</strong>
          <span class="n8n-node-type">{{ caption }}</span>
        </div>
      </div>
      <p class="n8n-node-preview">{{ preview }}</p>
      <div v-if="hints?.length" class="n8n-node-vars">
        <span
          v-for="hint in hints"
          :key="hint.name"
          class="var-chip"
          :class="`is-${hint.mark}`"
          :title="hintTitle(hint.mark)"
        >
          {{ hint.name }}
        </span>
      </div>
      <p v-if="hints?.some(hint => hint.mark === 'undefined')" class="n8n-node-var-warning">{{ t('nodePreview.varUndefined') }}</p>
      <div v-if="kind === 'if_else'" class="if-else-outputs">
        <div class="if-else-row">
          <span class="if-else-label is-true">TRUE</span>
          <Handle
            :id="`${nodeId}-true`"
            type="source"
            :position="Position.Right"
            class="n8n-handle n8n-handle-out"
          />
        </div>
        <div class="if-else-row">
          <span class="if-else-label is-false">FALSE</span>
          <Handle
            :id="`${nodeId}-false`"
            type="source"
            :position="Position.Right"
            class="n8n-handle n8n-handle-out"
          />
        </div>
      </div>
    </div>
    <Handle
      v-if="kind !== 'if_else'"
      :id="`${nodeId}-out`"
      type="source"
      :position="Position.Right"
      class="n8n-handle n8n-handle-out"
    />
  </div>
</template>
