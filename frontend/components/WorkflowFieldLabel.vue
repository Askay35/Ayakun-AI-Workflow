<script setup lang="ts">
defineProps<{
  text: string
  hint: string
}>()
</script>

<template>
  <span class="inline-flex items-center gap-1.5">
    <span>{{ text }}</span>
    <UTooltip :text="hint" :content="{ side: 'top' }">
      <UIcon name="i-lucide-info" class="size-3.5 shrink-0 opacity-60 cursor-help" />
    </UTooltip>
  </span>
</template>
