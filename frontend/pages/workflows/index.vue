<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'

import { formatCredits } from '~/utils/credits'

definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const { t, formatDateOnly } = useI18n()
const isMobileEditor = useIsMobileEditor()
const showMobileGate = ref(false)
const name = ref('')
const creating = ref(false)
const deletingId = ref<string>()
const renamingId = ref<string>()
const nameDraft = ref('')
const renamingBusy = ref(false)
const { data: workflows, pending, refresh } = await useAuthAsyncData('workflows', () => api.workflows.list())

const create = async () => {
  if (!name.value.trim()) return
  if (isMobileEditor.value) {
    showMobileGate.value = true
    return
  }
  creating.value = true
  try {
    const workflow = await api.workflows.create({ name: name.value, description: '' })
    await navigateTo(`/workflows/${workflow.id}`)
  } catch (error: any) {
    toast.add({ title: t('workflows.createError'), description: error?.data?.detail, color: 'error' })
  } finally { creating.value = false }
}

const openWorkflow = async (id: string) => {
  if (isMobileEditor.value) {
    showMobileGate.value = true
    return
  }
  await navigateTo(`/workflows/${id}`)
}

const remove = async (id: string, workflowName: string) => {
  if (!confirm(t('workflows.deleteConfirm', { name: workflowName }))) return
  deletingId.value = id
  try {
    await api.workflows.delete(id)
    workflows.value = (workflows.value || []).filter(workflow => workflow.id !== id)
    toast.add({ title: t('workflows.deleted'), color: 'success' })
    await refresh()
  } catch (error) {
    toast.add({ title: t('workflows.deleteError'), description: apiErrorMessage(error, t('common.genericError')), color: 'error' })
  } finally {
    deletingId.value = undefined
  }
}

const startRename = (workflowId: string, workflowName: string) => {
  renamingId.value = workflowId
  nameDraft.value = workflowName
}

const cancelRename = () => {
  renamingId.value = undefined
  nameDraft.value = ''
}

const commitRename = async (workflowId: string) => {
  const next = nameDraft.value.trim()
  if (!next) {
    toast.add({ title: t('workflows.nameRequired'), color: 'error' })
    return
  }
  renamingBusy.value = true
  try {
    const saved = await api.workflows.rename(workflowId, next)
    workflows.value = (workflows.value || []).map(item => item.id === saved.id ? { ...item, name: saved.name } : item)
    cancelRename()
    toast.add({ title: t('workflows.renamed'), color: 'success' })
  } catch (error) {
    toast.add({ title: t('workflows.renameError'), description: apiErrorMessage(error, t('common.genericError')), color: 'error' })
  } finally {
    renamingBusy.value = false
  }
}
</script>

<template>
  <WorkflowEditorUnavailable v-if="showMobileGate" embedded @close="showMobileGate = false" />
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">{{ t('workflows.eyebrow') }}</p>
        <h1 class="page-title">{{ t('workflows.title') }}</h1>
        <p class="muted">{{ t('workflows.lead') }}</p>
      </div>
    </div>
    <div class="panel mb-6 p-4">
      <div class="flex flex-col gap-3 sm:flex-row">
        <UInput v-model="name" :placeholder="t('workflows.placeholder')" size="lg" icon="i-lucide-wand-sparkles" class="flex-1" @keyup.enter="create" />
        <UButton :label="t('workflows.create')" size="lg" icon="i-lucide-plus" :loading="creating" @click="create" />
        <UButton to="/workflows/templates" :label="t('templates.fromTemplate')" size="lg" icon="i-lucide-layout-template" color="neutral" variant="outline" />
      </div>
    </div>
    <div v-if="pending" class="flex-cards"><div v-for="i in 3" :key="i" class="panel h-52 animate-pulse" /></div>
    <div v-else-if="workflows?.length" class="flex-cards">
      <div v-for="workflow in workflows" :key="workflow.id" class="panel workflow-card">
        <div class="flex items-start justify-between gap-3">
          <button type="button" class="workflow-card-icon" @click="openWorkflow(workflow.id)">
            <UIcon name="i-lucide-workflow" class="size-5" />
          </button>
          <div class="flex items-center gap-1">
            <span class="cost-pill"><UIcon name="i-lucide-coins" />{{ t('workflows.costUpTo', { cost: formatCredits(workflow.estimated_run_cost) }) }}</span>
            <UButton
              icon="i-lucide-pencil"
              color="neutral"
              variant="ghost"
              size="sm"
              :aria-label="t('workflows.renameAria')"
              @click="startRename(workflow.id, workflow.name)"
            />
            <UButton
              icon="i-lucide-trash-2"
              color="error"
              variant="ghost"
              size="sm"
              :loading="deletingId === workflow.id"
              :aria-label="t('workflows.deleteAria')"
              @click="remove(workflow.id, workflow.name)"
            />
          </div>
        </div>
        <div v-if="renamingId === workflow.id" class="mt-5 space-y-3">
          <UInput
            v-model="nameDraft"
            autofocus
            size="lg"
            maxlength="160"
            class="w-full"
            @keyup.enter="commitRename(workflow.id)"
            @keyup.escape="cancelRename"
          />
          <div class="flex gap-2">
            <UButton :label="t('common.save')" size="sm" :loading="renamingBusy" @click="commitRename(workflow.id)" />
            <UButton :label="t('common.cancel')" size="sm" variant="ghost" color="neutral" @click="cancelRename" />
          </div>
        </div>
        <button v-else type="button" class="block w-full cursor-pointer text-left" @click="openWorkflow(workflow.id)">
          <h2 class="mb-2 mt-5 text-xl font-extrabold tracking-tight">{{ workflow.name }}</h2>
          <p class="mb-6 text-sm muted">{{ workflow.next_run_at || workflow.schedule_cron ? t('workflows.auto') : t('workflows.manual') }}</p>
          <div class="workflow-card-footer">
            <div class="flex items-center gap-2"><span class="status-dot" :class="{ online: workflow.status === 'published' }" /><span class="text-xs font-bold">{{ workflow.status === 'published' ? t('workflows.published') : t('workflows.draft') }}</span></div>
            <span class="text-xs muted">{{ t('workflows.updated', { date: formatDateOnly(workflow.updated_at) }) }}</span>
          </div>
        </button>
      </div>
    </div>
    <div v-else class="panel py-16 text-center">
      <span class="mx-auto mb-4 grid size-16 place-items-center rounded-2xl bg-[var(--violet-soft)] text-[var(--violet)]"><UIcon name="i-lucide-workflow" class="size-7" /></span>
      <h2 class="mb-2 text-xl font-extrabold">{{ t('workflows.emptyTitle') }}</h2>
      <p class="mx-auto mb-0 max-w-md muted">{{ t('workflows.emptyText') }}</p>
    </div>
  </div>
</template>
