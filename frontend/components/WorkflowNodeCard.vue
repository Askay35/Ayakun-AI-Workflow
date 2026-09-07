<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { WorkflowNode } from '~/types/api'
const props = defineProps<{ data: WorkflowNode['data']; selected?: boolean }>()
const icon = computed(() => {
  if (props.data.status === 'running') return 'i-lucide-loader-circle'
  const label = props.data.label.toLowerCase()
  if (label.includes('поиск')) return 'i-lucide-search'
  if (label.includes('telegram')) return 'i-lucide-send'
  return 'i-lucide-sparkles'
})
</script>

<template>
  <div class="node-card" :class="{ active: selected }">
    <Handle type="target" :position="Position.Left" />
    <div class="flex items-center gap-2">
      <span class="grid size-9 shrink-0 place-items-center rounded-xl bg-[#efedff] text-[#6758ee]">
        <UIcon :name="icon" :class="{ 'animate-spin': data.status === 'running' }" />
      </span>
      <div class="min-w-0">
        <strong class="block truncate">{{ data.label }}</strong>
        <span class="text-[10px] font-bold uppercase tracking-wider muted">{{ data.status || 'Готов к настройке' }}</span>
      </div>
    </div>
    <p v-if="data.output" class="mt-2 max-w-52 truncate text-xs muted">{{ data.output }}</p>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
