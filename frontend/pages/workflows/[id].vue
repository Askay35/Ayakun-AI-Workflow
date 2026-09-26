<script setup lang="ts">
import type { Workflow } from '~/types/api'

definePageMeta({ layout: 'editor', middleware: 'auth', ssr: false })

const route = useRoute()
const api = useApi()
const isMobileEditor = useIsMobileEditor()
const workflowId = String(route.params.id)
// Тот же ключ, что у редакторов: цепочка грузится один раз, а режим (холст или шаги) зависит от неё.
const { data: workflow } = await useAuthAsyncData<Workflow>(`workflow-${workflowId}`, () => api.workflows.get(workflowId))
</script>

<template>
  <LazyWorkflowStepsEditor v-if="workflow?.mobile" :workflow-id="workflowId" />
  <WorkflowEditorUnavailable v-else-if="isMobileEditor" />
  <LazyWorkflowEditorCanvas v-else :workflow-id="workflowId" />
</template>
