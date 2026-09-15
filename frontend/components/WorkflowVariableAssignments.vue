<script setup lang="ts">
import { VARIABLE_NAME_RE } from '~/utils/workflow-variables'

const props = defineProps<{
  items: Array<{ key: string; value: string }>
}>()

const emit = defineEmits<{
  'update:items': [value: Array<{ key: string; value: string }>]
}>()

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

const assignmentExample = '{{total}} = {{$data[0].price}}'
</script>

<template>
  <div class="editor-assign">
    <p class="mb-1 text-[13px] font-extrabold text-white">Запись в переменные</p>
    <p class="mb-3 text-[11px] leading-5 text-white/40">После выполнения можно сохранить поле вывода: <code>{{ assignmentExample }}</code></p>
    <div v-for="(item, index) in items" :key="index" class="editor-assign-row">
      <UInput
        :model-value="item.key"
        placeholder="переменная"
        size="sm"
        class="w-full"
        :color="keyInvalid(item.key) ? 'error' : undefined"
        @update:model-value="updateRow(index, { key: String($event).replace(/^\{\{|\}\}$/g, '') })"
      />
      <UInput
        :model-value="item.value"
        placeholder="значение"
        size="sm"
        class="w-full font-mono"
        @update:model-value="updateRow(index, { value: String($event) })"
      />
      <button type="button" class="editor-var-remove" aria-label="Удалить присваивание" @click="removeRow(index)">
        <UIcon name="i-lucide-x" class="size-3.5" />
      </button>
    </div>
    <UButton
      label="Добавить запись"
      icon="i-lucide-plus"
      color="neutral"
      variant="ghost"
      size="sm"
      class="px-0 text-white/70"
      @click="addRow"
    />
  </div>
</template>
