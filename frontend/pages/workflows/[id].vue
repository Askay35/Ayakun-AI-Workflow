<script setup lang="ts">
definePageMeta({ layout: 'editor', middleware: 'auth', ssr: false })

const route = useRoute()
const isMobileEditor = useIsMobileEditor()
const workflowId = String(route.params.id)
</script>

<template>
  <WorkflowEditorUnavailable v-if="isMobileEditor" />
  <LazyWorkflowEditorCanvas v-else :workflow-id="workflowId" />
</template>
