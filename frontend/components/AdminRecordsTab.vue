<script setup lang="ts" generic="T extends Record<string, any>">
export type AdminFieldType = 'text' | 'number' | 'textarea' | 'select' | 'switch'

export interface AdminSelectOption {
  label: string
  value: string | number | boolean
}

export interface AdminField {
  key: string
  label: string
  type: AdminFieldType
  options?: AdminSelectOption[]
  step?: string
  hint?: string
  placeholder?: string
}

export interface AdminColumn {
  key: string
  label: string
  class?: string
}

const props = withDefaults(defineProps<{
  title?: string
  searchPlaceholder?: string
  statusOptions?: AdminSelectOption[]
  columns: AdminColumn[]
  fields: AdminField[]
  items: T[]
  total: number
  page: number
  pageSize?: number
  loading?: boolean
  saving?: boolean
  deleting?: boolean
  q: string
  status?: string
  editTitle?: string
  deleteTitle?: string
  deleteText?: (row: T) => string
  onSave?: (row: T, form: Record<string, unknown>) => Promise<boolean | void> | boolean | void
  onRemove?: (row: T) => Promise<boolean | void> | boolean | void
}>(), {
  searchPlaceholder: 'Поиск',
  statusOptions: () => [],
  pageSize: 20,
  loading: false,
  saving: false,
  deleting: false,
  status: '',
  editTitle: 'Редактировать запись',
  deleteTitle: 'Удалить запись',
  deleteText: (row: T) => `Удалить запись ${String(row.id)}? Это действие нельзя отменить.`
})

const emit = defineEmits<{
  'update:q': [value: string]
  'update:status': [value: string]
  'update:page': [value: number]
  open: [row: T]
}>()

const toast = useToast()
const editOpen = ref(false)
const deleteOpen = ref(false)
const current = ref<T | null>(null)
const form = reactive<Record<string, unknown>>({})

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const rangeLabel = computed(() => {
  if (!props.total) return 'Нет записей'
  const from = (props.page - 1) * props.pageSize + 1
  const to = Math.min(props.page * props.pageSize, props.total)
  return `${from}–${to} из ${props.total}`
})
const deleteMessage = computed(() => {
  const row = current.value
  return row ? props.deleteText(row) : ''
})

const openEdit = (row: T) => {
  current.value = row
  for (const field of props.fields) {
    const value = row[field.key]
    form[field.key] = value == null ? (field.type === 'switch' ? false : '') : value
  }
  emit('open', row)
  editOpen.value = true
}

const openDelete = (row: T) => {
  current.value = row
  deleteOpen.value = true
}

const submitEdit = async () => {
  if (!current.value) return
  const payload: Record<string, unknown> = {}
  for (const field of props.fields) {
    let value = form[field.key]
    if (field.type === 'number' && value !== '' && value != null) value = Number(value)
    if (field.type === 'text' || field.type === 'textarea') {
      if (typeof value === 'string') value = value.trim()
    }
    payload[field.key] = value === '' ? null : value
  }
  const ok = await props.onSave?.(current.value, payload)
  if (ok !== false) editOpen.value = false
}

const confirmDelete = async () => {
  if (!current.value) return
  const ok = await props.onRemove?.(current.value)
  if (ok !== false) deleteOpen.value = false
}

const closeEdit = () => {
  editOpen.value = false
}

const copyValue = async (value: string | number) => {
  try {
    await navigator.clipboard.writeText(String(value))
    toast.add({ title: 'Скопировано', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось скопировать', color: 'error' })
  }
}

defineExpose({ closeEdit, openEdit, copyValue })
</script>

<template>
  <div class="admin-records">
    <div class="admin-toolbar">
      <UInput
        :model-value="q"
        :placeholder="searchPlaceholder"
        icon="i-lucide-search"
        class="admin-search"
        @update:model-value="emit('update:q', String($event ?? ''))"
      />
      <USelect
        v-if="statusOptions.length"
        :model-value="status || 'all'"
        :items="statusOptions"
        value-key="value"
        class="admin-filter"
        @update:model-value="emit('update:status', $event === 'all' ? '' : String($event))"
      />
      <p class="admin-range">{{ rangeLabel }}</p>
    </div>

    <div class="admin-table-wrap">
      <div v-if="loading" class="admin-table-loading">
        <USkeleton v-for="i in 6" :key="i" class="h-12" />
      </div>
      <table v-else class="admin-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.key" :class="column.class">{{ column.label }}</th>
            <th class="admin-col-actions">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td :colspan="columns.length + 1" class="admin-empty">Ничего не найдено</td>
          </tr>
          <tr v-for="row in items" :key="String(row.id)">
            <td v-for="column in columns" :key="column.key" :class="column.class">
              <slot :name="column.key" :row="row" :copy="copyValue">{{ row[column.key] ?? '—' }}</slot>
            </td>
            <td class="admin-col-actions">
              <div class="admin-row-actions">
                <slot name="actions" :row="row" />
                <UButton icon="i-lucide-pencil" color="neutral" variant="soft" size="sm" aria-label="Изменить" @click="openEdit(row)" />
                <UButton icon="i-lucide-trash-2" color="error" variant="soft" size="sm" aria-label="Удалить" @click="openDelete(row)" />
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="pageCount > 1" class="admin-pager">
      <UPagination
        :page="page"
        :total="total"
        :items-per-page="pageSize"
        :sibling-count="1"
        show-edges
        @update:page="emit('update:page', $event)"
      />
    </div>

    <UModal
      :open="editOpen"
      :title="editTitle"
      :ui="{ footer: 'justify-end', 
      content: 'bg-[#fff]!important',
      header: '[&_h2]:text-white!' }"
      @update:open="editOpen = $event"
    >
      <template #body>
        <form class="admin-edit-form" @submit.prevent="submitEdit">
          <div v-for="field in fields" :key="field.key">
            <UFormField :label="field.label" :hint="field.hint">
              <UInput
                v-if="field.type === 'text' || field.type === 'number'"
                :model-value="form[field.key] as string | number | undefined"
                :type="field.type === 'number' ? 'number' : 'text'"
                :step="field.step"
                :placeholder="field.placeholder"
                class="w-full"
                @update:model-value="form[field.key] = $event"
              />
              <UTextarea
                v-else-if="field.type === 'textarea'"
                :model-value="String(form[field.key] ?? '')"
                :placeholder="field.placeholder"
                :rows="3"
                class="w-full"
                @update:model-value="form[field.key] = $event"
              />
              <USelect
                v-else-if="field.type === 'select'"
                :model-value="form[field.key] as string | number | boolean | undefined"
                :items="field.options || []"
                value-key="value"
                class="w-full"
                @update:model-value="form[field.key] = $event"
              />
              <USwitch
                v-else-if="field.type === 'switch'"
                :model-value="Boolean(form[field.key])"
                @update:model-value="form[field.key] = $event"
              />
            </UFormField>
          </div>
          <slot name="edit-extra" :row="current" :form="form" />
        </form>
      </template>
      <template #footer="{ close }">
        <UButton label="Отмена" color="neutral" variant="outline" :disabled="saving" @click="close" />
        <UButton label="Сохранить" :loading="saving" @click="submitEdit" />
      </template>
    </UModal>

    <UModal
      :open="deleteOpen"
      :title="deleteTitle"
      :ui="{ footer: 'justify-end' }"
      @update:open="deleteOpen = $event"
    >
      <template #body>
        <p class="mb-0 text-[15px] leading-6">{{ deleteMessage }}</p>
      </template>
      <template #footer="{ close }">
        <UButton label="Отмена" color="neutral" variant="outline" :disabled="deleting" @click="close" />
        <UButton label="Удалить" color="error" :loading="deleting" @click="confirmDelete" />
      </template>
    </UModal>
  </div>
</template>
