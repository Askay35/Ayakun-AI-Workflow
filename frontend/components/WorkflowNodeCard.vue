<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { WorkflowNode } from '~/types/api'
defineProps<{ data: WorkflowNode['data']; selected?: boolean }>()
</script>

<template>
  <div class="min-w-48 rounded-xl border-2 bg-white p-3 shadow-sm" :class="selected ? 'border-primary' : 'border-default'">
    <Handle type="target" :position="Position.Left" />
    <div class="flex items-center gap-2">
      <UIcon :name="data.status === 'running' ? 'i-lucide-loader-circle' : 'i-lucide-sparkles'" :class="{ 'animate-spin': data.status === 'running' }" />
      <strong>{{ data.label }}</strong>
      <UBadge v-if="data.status" :label="data.status" size="xs" variant="soft" />
    </div>
    <p v-if="data.output" class="mt-2 max-w-52 truncate text-xs muted">{{ data.output }}</p>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
