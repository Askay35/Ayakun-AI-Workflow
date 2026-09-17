<script setup lang="ts">
import { BaseEdge, getBezierPath, Position, type EdgeProps } from '@vue-flow/core'

const props = defineProps<EdgeProps>()
const emit = defineEmits<{
  remove: [id: string]
}>()
const { t } = useI18n()

const path = computed(() => {
  const [d, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition ?? Position.Right,
    targetPosition: props.targetPosition ?? Position.Left
  })
  return { d, labelX, labelY }
})

const removeEdge = (event: Event) => {
  event.preventDefault()
  event.stopPropagation()
  emit('remove', props.id)
}
</script>

<template>
  <g>
    <BaseEdge
      :id="id"
      :path="path.d"
      :marker-end="markerEnd"
      :marker-start="markerStart"
      :style="style"
      :interaction-width="interactionWidth ?? 28"
    />
    <g
      class="edge-delete nodrag nopan"
      :transform="`translate(${path.labelX}, ${path.labelY})`"
      @click="removeEdge"
      @pointerdown.stop
      @mousedown.stop
    >
      <title>{{ t('editor.deleteEdge') }}</title>
      <circle class="edge-delete-hit" r="14" />
      <circle r="11" />
      <path d="M-4 -4 L4 4 M4 -4 L-4 4" />
    </g>
  </g>
</template>
