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

const meta = computed(() => NODE_META[props.kind])
const preview = computed(() => {
  if (props.kind === 'web_search') return props.data.query?.trim() || 'Запрос ещё не задан'
  if (props.kind === 'prompt') return props.data.prompt?.trim() || 'Инструкция ещё не задана'
  if (props.kind === 'http_request') return props.data.request_json?.trim() || 'Данные запроса ещё не заданы'
  if (props.kind === 'if_else') return props.data.condition?.trim() || 'Условие ещё не задано'
  if (props.kind === 'telegram_send') {
    const text = props.data.message?.trim()
    if (text) return text
    return props.data.chat_id ? `Чат ${props.data.chat_id}` : 'В ваш Telegram'
  }
  if (props.kind === 'webhook') return 'Ждёт событие из внешнего сервиса'
  if (props.kind === 'google_sheets') {
    const operation = props.data.operation === 'append' ? 'Добавить строки' : props.data.operation === 'update' ? 'Обновить строки' : 'Читать строки'
    return props.data.spreadsheet_id?.trim() ? `${operation} · ${props.data.spreadsheet_id}` : operation
  }
  if (props.kind === 'gmail') {
    if (props.data.operation === 'list') return props.data.gmail_query?.trim() || 'Получить письма'
    return props.data.to?.trim() ? `Кому: ${props.data.to}` : 'Отправить письмо'
  }
  if (props.kind === 'data_transform') {
    const names: Record<string, string> = {
      select: 'Select — оставить поля',
      rename: 'Rename — переименовать',
      set: 'Set — задать значения',
      remove: 'Remove — удалить поля',
      filter: 'Filter — отфильтровать',
      sort: 'Sort — сортировка',
      map: 'Map — преобразовать элементы'
    }
    return names[props.data.operation || 'select'] || 'Преобразование данных'
  }
  if (props.kind === 'sql_query') return props.data.query?.trim() || 'SQL-запрос ещё не задан'
  return props.data.label || meta.value.label
})
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
          <strong class="n8n-node-title">{{ data.label || meta.label }}</strong>
          <span class="n8n-node-type">{{ meta.caption }}</span>
        </div>
      </div>
      <p class="n8n-node-preview">{{ preview }}</p>
      <div v-if="hints?.length" class="n8n-node-vars">
        <span
          v-for="hint in hints"
          :key="hint.name"
          class="var-chip"
          :class="`is-${hint.mark}`"
          :title="hint.mark === 'undefined' ? 'Переменная пока не определена' : hint.mark === 'write' ? 'Создаётся или обновляется этим блоком' : 'Используется, не изменяется'"
        >
          {{ hint.name }}
        </span>
      </div>
      <p v-if="hints?.some(hint => hint.mark === 'undefined')" class="n8n-node-var-warning">Переменная пока не определена</p>
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
