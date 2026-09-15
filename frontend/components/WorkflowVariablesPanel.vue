<script setup lang="ts">
import { VARIABLE_NAME_RE, type VariableRow } from '~/utils/workflow-variables'

const props = defineProps<{
  items: VariableRow[]
}>()

const emit = defineEmits<{
  'update:items': [value: VariableRow[]]
}>()

const addVariable = () => {
  emit('update:items', [...props.items, { key: '', value: '' }])
}

const updateRow = (index: number, patch: Partial<VariableRow>) => {
  emit('update:items', props.items.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
}

const removeRow = (index: number) => {
  emit('update:items', props.items.filter((_, rowIndex) => rowIndex !== index))
}

const keyError = (key: string) => {
  const trimmed = key.trim()
  if (!trimmed) return ''
  if (!VARIABLE_NAME_RE.test(trimmed)) return 'Только латиница, цифры и _'
  return ''
}

const variableNameExample = '{{name}}'
</script>

<template>
  <div class="editor-vars">
    <p class="mb-1 text-sm font-extrabold text-white">Переменные</p>
    <p class="mb-3 text-[11px] leading-5 text-white/40">Доступны в звеньях как <code>{{ variableNameExample }}</code>. Значение можно перезаписать.</p>
    <div v-if="items.length" class="editor-var-list">
      <div v-for="(item, index) in items" :key="index" class="editor-var-row">
        <UInput
          :model-value="item.key"
          placeholder="ключ"
          size="sm"
          class="w-full"
          :color="keyError(item.key) ? 'error' : undefined"
          @update:model-value="updateRow(index, { key: String($event) })"
        />
        <UInput
          :model-value="item.value"
          placeholder="значение"
          size="sm"
          class="w-full"
          @update:model-value="updateRow(index, { value: String($event) })"
        />
        <button type="button" class="editor-var-remove" aria-label="Удалить переменную" @click="removeRow(index)">
          <UIcon name="i-lucide-x" class="size-3.5" />
        </button>
        <p v-if="keyError(item.key)" class="editor-var-error">{{ keyError(item.key) }}</p>
      </div>
    </div>
    <UButton
      label="Добавить"
      icon="i-lucide-plus"
      color="neutral"
      variant="soft"
      block
      size="sm"
      class="mt-2"
      @click="addVariable"
    />
  </div>
</template>
