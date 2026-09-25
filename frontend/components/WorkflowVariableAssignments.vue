<script setup lang="ts">
import { VARIABLE_NAME_RE } from '~/utils/workflow-variables'

const props = defineProps<{
  items: Array<{ key: string; value: string }>
}>()

const emit = defineEmits<{
  'update:items': [value: Array<{ key: string; value: string }>]
}>()

const { t } = useI18n()

const addRow = () => {
  emit('update:items', [...props.items, { key: '', value: '' }])
}

const updateRow = (index: number, patch: Partial<{ key: string; value: string }>) => {
  emit('update:items', props.items.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
}

const removeRow = (index: number) => {
  emit('update:items', props.items.filter((_, rowIndex) => rowIndex !== index))
}

const keyInvalid = (key: string) => {
  const trimmed = key.trim()
  return trimmed.length > 0 && !VARIABLE_NAME_RE.test(trimmed)
}

const assignmentExample = '{{total}} = {{$data[0].field}}'
</script>

<template>
  <div class="editor-assign">
    <p class="editor-panel-title">{{ t('vars.assignTitle') }}</p>
    <p class="editor-hint mb-3">{{ t('vars.assignHint', { example: assignmentExample }) }}</p>
    <div v-for="(item, index) in items" :key="index" class="editor-assign-row">
      <UInput
        :model-value="item.key"
        :placeholder="t('vars.assignKey')"
        size="sm"
        class="w-full"
        :color="keyInvalid(item.key) ? 'error' : undefined"
        @update:model-value="updateRow(index, { key: String($event).replace(/^\{\{|\}\}$/g, '') })"
      />
      <UInput
        :model-value="item.value"
        :placeholder="t('vars.value')"
        size="sm"
        class="w-full font-mono"
        @update:model-value="updateRow(index, { value: String($event) })"
      />
      <button type="button" class="editor-var-remove" :aria-label="t('vars.assignRemove')" @click="removeRow(index)">
        <UIcon name="i-lucide-x" class="size-3.5" />
      </button>
    </div>
    <UButton
      :label="t('vars.assignAdd')"
      icon="i-lucide-plus"
      color="primary"
      variant="ghost"
      size="sm"
      class="px-0"
      @click="addRow"
    />
  </div>
</template>
