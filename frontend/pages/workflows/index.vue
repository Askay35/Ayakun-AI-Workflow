<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'

import { formatCredits } from '~/utils/credits'

definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const name = ref('')
const creating = ref(false)
const deletingId = ref<string>()
const { data: workflows, pending, refresh } = await useAuthAsyncData('workflows', () => api.workflows.list())

const create = async () => {
  if (!name.value.trim()) return
  creating.value = true
  try {
    const workflow = await api.workflows.create({ name: name.value, description: '' })
    await navigateTo(`/workflows/${workflow.id}`)
  } catch (error: any) {
    toast.add({ title: 'Не удалось создать цепочку', description: error?.data?.detail, color: 'error' })
  } finally { creating.value = false }
}

const remove = async (id: string, workflowName: string) => {
  if (!confirm(`Удалить цепочку «${workflowName}»? Это действие нельзя отменить.`)) return
  deletingId.value = id
  try {
    await api.workflows.delete(id)
    workflows.value = (workflows.value || []).filter(workflow => workflow.id !== id)
    toast.add({ title: 'Цепочка удалена', color: 'success' })
    await refresh()
  } catch (error) {
    toast.add({ title: 'Не удалось удалить', description: apiErrorMessage(error), color: 'error' })
  } finally {
    deletingId.value = undefined
  }
}

const formatCost = (value?: number) => `${formatCredits(value)} credits`
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">Мои автоматизации</p>
        <h1 class="page-title">Цепочки</h1>
        <p class="muted">Всё, что Ayakun делает за вас — вручную или по расписанию.</p>
      </div>
    </div>
    <div class="panel mb-6 p-4">
      <div class="flex flex-col gap-3 sm:flex-row">
        <UInput v-model="name" placeholder="Например: утренний обзор новостей" size="lg" icon="i-lucide-wand-sparkles" class="flex-1" @keyup.enter="create" />
        <UButton label="Создать цепочку" size="lg" icon="i-lucide-plus" :loading="creating" @click="create" />
      </div>
    </div>
    <div v-if="pending" class="grid-cards"><div v-for="i in 3" :key="i" class="panel h-52 animate-pulse bg-white/50" /></div>
    <div v-else-if="workflows?.length" class="grid-cards">
      <div v-for="workflow in workflows" :key="workflow.id" class="panel workflow-card">
        <div class="flex items-start justify-between gap-3">
          <NuxtLink :to="`/workflows/${workflow.id}`" class="grid size-11 place-items-center rounded-2xl bg-[#efedff] text-[#6758ee]">
            <UIcon name="i-lucide-workflow" class="size-5" />
          </NuxtLink>
          <div class="flex items-center gap-1">
            <span class="cost-pill"><UIcon name="i-lucide-coins" />{{ formatCost(workflow.estimated_run_cost) }} / запуск</span>
            <UButton
              icon="i-lucide-trash-2"
              color="error"
              variant="ghost"
              size="sm"
              :loading="deletingId === workflow.id"
              aria-label="Удалить цепочку"
              @click="remove(workflow.id, workflow.name)"
            />
          </div>
        </div>
        <NuxtLink :to="`/workflows/${workflow.id}`" class="block">
          <h2 class="mb-2 mt-5 text-xl font-extrabold">{{ workflow.name }}</h2>
          <p class="mb-5 text-sm muted">{{ workflow.schedule_cron ? 'Запускается автоматически' : 'Запуск вручную' }}</p>
          <div class="workflow-card-footer">
            <div class="flex items-center gap-2"><span class="status-dot" :class="{ online: workflow.status === 'published' }" /><span class="text-xs font-bold">{{ workflow.status === 'published' ? 'Активна' : 'Черновик' }}</span></div>
            <span class="text-xs muted">Изменена {{ new Date(workflow.updated_at).toLocaleDateString('ru') }}</span>
          </div>
        </NuxtLink>
      </div>
    </div>
    <div v-else class="panel py-16 text-center">
      <span class="mx-auto mb-4 grid size-16 place-items-center rounded-2xl bg-[#efedff] text-[#6758ee]"><UIcon name="i-lucide-workflow" class="size-7" /></span>
      <h2 class="mb-2 text-xl font-extrabold">Пока здесь пусто</h2>
      <p class="mx-auto mb-0 max-w-md muted">Придумайте название выше — и мы откроем редактор вашей первой автоматизации.</p>
    </div>
  </div>
</template>
