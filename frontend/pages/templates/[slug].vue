<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'

definePageMeta({ layout: 'app', middleware: 'auth' })
const route = useRoute()
const api = useApi()
const { t } = useI18n()
const isMobileEditor = useIsMobileEditor()
const error = ref('')
let started = false

const copy = async () => {
  if (started) return
  started = true
  error.value = ''
  try {
    const workflow = await api.templates.use(String(route.params.slug), isMobileEditor.value)
    await navigateTo(`/workflows/${workflow.id}`, { replace: true })
  } catch (reason) {
    started = false
    error.value = apiErrorMessage(reason, t('templates.copyError'))
  }
}

onMounted(copy)
</script>

<template>
  <div class="page grid min-h-[60vh] place-items-center">
    <div class="panel max-w-md p-8 text-center">
      <template v-if="!error">
        <span class="tile mx-auto mb-4"><UIcon name="i-lucide-copy-plus" class="size-5" /></span>
        <h1 class="mb-2 text-xl font-extrabold tracking-tight">{{ t('templates.copying') }}</h1>
        <p class="mb-0 text-sm muted">{{ t('templates.copyingHint') }}</p>
      </template>
      <template v-else>
        <span class="tile mx-auto mb-4"><UIcon name="i-lucide-circle-alert" class="size-5" /></span>
        <h1 class="mb-2 text-xl font-extrabold tracking-tight">{{ t('templates.copyError') }}</h1>
        <p class="mb-5 text-sm muted">{{ error }}</p>
        <div class="flex justify-center gap-2">
          <UButton :label="t('templates.retry')" icon="i-lucide-rotate-cw" @click="copy" />
          <UButton to="/workflows/templates" :label="t('templates.back')" color="neutral" variant="ghost" />
        </div>
      </template>
    </div>
  </div>
</template>
