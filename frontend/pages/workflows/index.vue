<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const name = ref('')
const creating = ref(false)
const { data: workflows, refresh, pending } = await useAsyncData('workflows', () => api.workflows.list())

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
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1 class="text-3xl font-bold">Цепочки</h1><p class="muted">Черновики и опубликованные автоматизации.</p></div></div>
    <UCard class="mb-5">
      <div class="flex gap-2"><UInput v-model="name" placeholder="Название новой цепочки" class="flex-1" @keyup.enter="create" /><UButton label="Создать" icon="i-lucide-plus" :loading="creating" @click="create" /></div>
    </UCard>
    <div v-if="pending" class="grid-cards"><USkeleton v-for="i in 3" :key="i" class="h-36" /></div>
    <div v-else-if="workflows?.length" class="grid-cards">
      <UCard v-for="workflow in workflows" :key="workflow.id">
        <div class="flex items-start justify-between"><UIcon name="i-lucide-workflow" class="size-8 text-primary" /><UBadge :label="workflow.status === 'published' ? 'Опубликована' : 'Черновик'" variant="soft" /></div>
        <h2 class="mt-4 text-lg font-semibold">{{ workflow.name }}</h2><p class="mt-1 text-sm muted">Изменена {{ new Date(workflow.updated_at).toLocaleString('ru') }}</p>
        <UButton :to="`/workflows/${workflow.id}`" label="Открыть редактор" variant="link" class="mt-3 px-0" />
      </UCard>
    </div>
    <UCard v-else class="text-center"><p class="muted">Создайте первую цепочку выше.</p></UCard>
  </div>
</template>
