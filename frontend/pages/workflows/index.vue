<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const name = ref('')
const creating = ref(false)
const { data: workflows, pending } = await useAsyncData('workflows', () => api.workflows.list())

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

const formatCost = (value?: number) => `${Number(value || 0).toLocaleString('ru', { maximumFractionDigits: 2 })} credits`
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
      <NuxtLink v-for="workflow in workflows" :key="workflow.id" :to="`/workflows/${workflow.id}`" class="panel workflow-card">
        <div class="flex items-start justify-between gap-3">
          <span class="grid size-11 place-items-center rounded-2xl bg-[#efedff] text-[#6758ee]"><UIcon name="i-lucide-workflow" class="size-5" /></span>
          <span class="cost-pill"><UIcon name="i-lucide-coins" />{{ formatCost(workflow.estimated_run_cost) }} / запуск</span>
        </div>
        <h2 class="mb-2 mt-5 text-xl font-extrabold">{{ workflow.name }}</h2>
        <p class="mb-5 text-sm muted">{{ workflow.schedule_cron ? 'Запускается автоматически' : 'Запуск вручную' }}</p>
        <div class="workflow-card-footer">
          <div class="flex items-center gap-2"><span class="status-dot" :class="{ online: workflow.status === 'published' }" /><span class="text-xs font-bold">{{ workflow.status === 'published' ? 'Активна' : 'Черновик' }}</span></div>
          <span class="text-xs muted">Изменена {{ new Date(workflow.updated_at).toLocaleDateString('ru') }}</span>
        </div>
      </NuxtLink>
    </div>
    <div v-else class="panel py-16 text-center">
      <span class="mx-auto mb-4 grid size-16 place-items-center rounded-2xl bg-[#efedff] text-[#6758ee]"><UIcon name="i-lucide-workflow" class="size-7" /></span>
      <h2 class="mb-2 text-xl font-extrabold">Пока здесь пусто</h2>
      <p class="mx-auto mb-0 max-w-md muted">Придумайте название выше — и мы откроем редактор вашей первой автоматизации.</p>
    </div>
  </div>
</template>
