<script setup lang="ts">
import { MarkerType, VueFlow, useVueFlow, type Connection } from '@vue-flow/core'
import type { NodeKind, WorkflowEdge, WorkflowNode } from '~/types/api'

definePageMeta({ layout: 'app', middleware: 'auth', ssr: false })
const route = useRoute()
const api = useApi()
const toast = useToast()
const id = String(route.params.id)
const flowId = `workflow-${id}`

const { data: workflow, error: workflowError } = await useAsyncData(`workflow-${id}`, () => api.workflows.get(id))
if (workflowError.value || !workflow.value) {
  throw createError({ statusCode: 404, statusMessage: 'Цепочка не найдена', fatal: false })
}

const nodes = ref<WorkflowNode[]>(structuredClone(toRaw(workflow.value.draft_graph?.nodes || [])))
const edges = ref<WorkflowEdge[]>(structuredClone(toRaw(workflow.value.draft_graph?.edges || [])))
const scheduleEnabled = ref(Boolean(workflow.value.schedule_cron))
const schedulePreset = ref(workflow.value.schedule_cron || '0 9 * * *')
const selectedId = ref<string>()
const selected = computed(() => nodes.value.find(node => node.id === selectedId.value))
const validationErrors = ref<string[]>([])
const saveState = ref<'saved' | 'saving' | 'dirty'>('saved')
const estimatedCost = ref(Number(workflow.value.estimated_run_cost || 0))
const { addEdges, screenToFlowCoordinate } = useVueFlow({ id: flowId })
let saveTimer: ReturnType<typeof setTimeout> | undefined

const palette: Array<{ type: NodeKind; label: string; icon: string }> = [
  { type: 'web_search', label: 'Поиск в сети', icon: 'i-lucide-search' },
  { type: 'prompt', label: 'Обработка', icon: 'i-lucide-sparkles' },
  { type: 'telegram_send', label: 'Telegram', icon: 'i-lucide-send' }
]
const schedulePresets = [
  { label: 'Каждый день в 9:00', value: '0 9 * * *' },
  { label: 'Каждый час', value: '0 * * * *' },
  { label: 'Пн–Пт в 10:00', value: '0 10 * * 1-5' },
  { label: 'Раз в неделю (пн 9:00)', value: '0 9 * * 1' }
]
const qualityModes = [
  { label: 'Быстрый', value: 'simple_text' },
  { label: 'Точный', value: 'complex_text' }
]

const save = async () => {
  saveState.value = 'saving'
  try {
    const saved = await api.workflows.save(id, { nodes: nodes.value, edges: edges.value }, {
      schedule_cron: scheduleEnabled.value ? schedulePreset.value : null,
      schedule_timezone: 'UTC'
    })
    workflow.value = saved
    estimatedCost.value = Number(saved.estimated_run_cost || 0)
    saveState.value = 'saved'
  } catch {
    saveState.value = 'dirty'
    toast.add({ title: 'Черновик не сохранён', color: 'error' })
  }
}
watch([nodes, edges, scheduleEnabled, schedulePreset], () => {
  saveState.value = 'dirty'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(save, 900)
}, { deep: true })
onBeforeUnmount(() => clearTimeout(saveTimer))

const onConnect = (connection: Connection) => addEdges({
  ...connection, id: crypto.randomUUID(), markerEnd: MarkerType.ArrowClosed
})
const onDragStart = (event: DragEvent, type: NodeKind) => event.dataTransfer?.setData('application/yakun-node', type)
const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/yakun-node') as NodeKind
  if (!type) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  const item = palette.find(entry => entry.type === type)!
  const node: WorkflowNode = {
    id: crypto.randomUUID(), type, position,
    data: {
      label: item.label,
      complexity: type === 'prompt' ? 'simple_text' : undefined
    }
  }
  nodes.value.push(node)
  selectedId.value = node.id
}
const validate = async () => {
  const result = await api.workflows.validate(id)
  validationErrors.value = result.errors
  toast.add({ title: result.valid ? 'Цепочка готова' : 'Есть ошибки', color: result.valid ? 'success' : 'warning' })
  return result.valid
}
const validateClick = async () => { await validate() }
const publish = async () => {
  await save()
  if (await validate()) {
    try {
      workflow.value = await api.workflows.publish(id)
      toast.add({ title: 'Цепочка опубликована', color: 'success' })
    } catch (error: any) {
      console.error(error)
      toast.add({ title: 'Ошибка публикации цепочки: ' + error.message, color: 'error' })
    }
  }
}
const run = async () => {
  await save()
  const result = await api.workflows.run(id)
  await navigateTo(`/runs/${result.id}`)
}
</script>

<template>
  <div class="flex h-[100dvh] min-w-0 flex-col overflow-hidden bg-[#f8f7f4]">
    <header class="flex min-h-[76px] shrink-0 items-center justify-between border-b border-default bg-white/90 px-5 py-3 backdrop-blur">
      <div class="flex items-center gap-3">
        <UButton to="/workflows" icon="i-lucide-arrow-left" color="neutral" variant="ghost" />
        <div>
          <h1 class="mb-0 font-extrabold">{{ workflow?.name }}</h1>
          <p class="mb-0 text-xs muted">{{ saveState === 'saving' ? 'Сохраняем изменения…' : saveState === 'saved' ? 'Все изменения сохранены' : 'Есть несохранённые изменения' }}</p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="cost-pill"><UIcon name="i-lucide-coins" />{{ Math.round(estimatedCost).toLocaleString('ru') }} ток. / запуск</span>
        <UButton label="Проверить" icon="i-lucide-circle-check" color="neutral" variant="ghost" @click="validateClick" />
        <UButton label="Сохранить версию" color="neutral" variant="outline" @click="publish" />
        <UButton label="Запустить сейчас" icon="i-lucide-play" @click="run" />
      </div>
    </header>
    <div class="grid min-h-0 flex-1 grid-cols-[190px_minmax(0,1fr)_300px]">
      <aside class="overflow-y-auto border-r border-default bg-white/90 p-3">
        <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">Действия</p>
        <p class="mb-4 text-[11px] leading-4 muted">Перетащите нужный блок на поле</p>
        <div
          v-for="item in palette"
          :key="item.type"
          draggable="true"
          class="mb-2 flex cursor-grab items-center rounded-xl border border-default bg-white p-3 text-sm font-bold transition hover:border-violet-300 hover:shadow-sm"
          @dragstart="onDragStart($event, item.type)"
        >
          <span class="mr-2 grid size-8 place-items-center rounded-lg bg-[#efedff] text-[#6758ee]"><UIcon :name="item.icon" /></span>{{ item.label }}
        </div>
        <div class="mt-6 space-y-3 rounded-xl border border-default p-3">
          <div class="flex items-center justify-between gap-2">
            <p class="mb-0 text-sm font-extrabold">Автозапуск</p>
            <USwitch v-model="scheduleEnabled" />
          </div>
          <p class="mb-0 text-xs leading-5 muted">Yakun запустит цепочку сам. Вы платите только за выполненные запуски.</p>
          <USelect
            v-if="scheduleEnabled"
            v-model="schedulePreset"
            :items="schedulePresets"
            value-key="value"
            class="w-full"
          />
        </div>
      </aside>
      <div class="flow-canvas min-h-0" @dragover.prevent @drop="onDrop">
        <ClientOnly>
          <VueFlow
            :id="flowId"
            v-model:nodes="nodes"
            v-model:edges="edges"
            fit-view-on-init
            @connect="onConnect"
            @node-click="selectedId = $event.node.id"
            @pane-click="selectedId = undefined"
          >
            <template #node-web_search="{ data, selected: active }"><WorkflowNodeCard :data="data" :selected="active" /></template>
            <template #node-prompt="{ data, selected: active }"><WorkflowNodeCard :data="data" :selected="active" /></template>
            <template #node-telegram_send="{ data, selected: active }"><WorkflowNodeCard :data="data" :selected="active" /></template>
          </VueFlow>
          <template #fallback>
            <div class="grid h-full place-items-center text-sm muted">Загрузка редактора…</div>
          </template>
        </ClientOnly>
      </div>
      <aside class="overflow-y-auto border-l border-default bg-white/90 p-4">
        <template v-if="selected">
          <div class="flex justify-between">
            <div><p class="mb-1 text-xs font-bold uppercase tracking-wider muted">Выбранное действие</p><h2 class="mb-0 font-extrabold">Настройки</h2></div>
            <UButton icon="i-lucide-trash-2" color="error" variant="ghost" @click="nodes = nodes.filter(n => n.id !== selectedId); edges = edges.filter(e => e.source !== selectedId && e.target !== selectedId)" />
          </div>
          <div class="mt-4 space-y-4">
            <UFormField label="Название блока"><UInput v-model="selected.data.label" class="w-full" /></UFormField>
            <UFormField v-if="selected.type === 'web_search'" label="Что нужно найти">
              <UTextarea v-model="selected.data.query" :rows="6" class="w-full" placeholder="Например: найди главные новости рынка за последние сутки" />
            </UFormField>
            <template v-if="selected.type === 'prompt'">
              <UFormField label="Глубина обработки">
                <USelect v-model="selected.data.complexity" :items="qualityModes" value-key="value" class="w-full" />
              </UFormField>
              <UFormField label="Что сделать с результатом">
                <UTextarea v-model="selected.data.prompt" :rows="7" class="w-full" placeholder="Например: выдели 5 главных фактов и сделай краткий вывод" />
              </UFormField>
              <p class="text-sm leading-5 muted">К инструкции автоматически добавится текст предыдущего блока.</p>
            </template>
            <template v-if="selected.type === 'telegram_send'">
              <UFormField label="Получатель"><UInput v-model="selected.data.chat_id" class="w-full" placeholder="Оставьте пустым для своего аккаунта" /></UFormField>
              <p class="text-sm leading-5 muted">Отправит в Telegram текст, который сформировал предыдущий блок (поиск или обработка). Шаблон не нужен — просто соедините блоки стрелкой.</p>
            </template>
          </div>
        </template>
        <div v-else>
          <p class="mb-1 text-xs font-bold uppercase tracking-wider muted">Параметры</p>
          <h2 class="font-extrabold">Выберите действие</h2>
          <p class="mt-2 text-sm leading-6 muted">Нажмите на блок на поле, чтобы настроить, что именно он должен сделать.</p>
          <div class="mt-6 panel !p-4">
            <p class="eyebrow">Цена запуска</p>
            <p class="mb-0 text-3xl font-extrabold">{{ Math.round(estimatedCost).toLocaleString('ru') }}</p>
            <p class="mb-0 mt-1 text-sm muted">токенов за выполнение всей цепочки</p>
          </div>
        </div>
        <div v-if="validationErrors.length" class="mt-6">
          <h3 class="font-semibold text-warning">Ошибки</h3>
          <ul class="mt-2 list-disc pl-5 text-sm"><li v-for="err in validationErrors" :key="err">{{ err }}</li></ul>
        </div>
      </aside>
    </div>
  </div>
</template>
