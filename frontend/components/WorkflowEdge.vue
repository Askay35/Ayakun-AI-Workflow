<script setup lang="ts">
import { BaseEdge, getSmoothStepPath, Position, type EdgeProps } from '@vue-flow/core'

const props = defineProps<EdgeProps>()
const emit = defineEmits<{
  remove: [id: string]
}>()
const { t } = useI18n()

const path = computed(() => {
  const [d, labelX, labelY] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition ?? Position.Right,
    targetPosition: props.targetPosition ?? Position.Left,
    borderRadius: 18
  })
  return { d, labelX, labelY }
})
const branch = computed(() => {
  const handle = String(props.sourceHandleId || '')
  if (handle.endsWith('true')) return 'true'
  if (handle.endsWith('false')) return 'false'
  return ''
})
const stroke = computed(() => {
  if (branch.value === 'true') return '#4ade80'
  if (branch.value === 'false') return '#f87171'
  return '#a99cff'
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
      :style="{ ...style, stroke, strokeWidth: 2 }"
      :interaction-width="interactionWidth ?? 32"
    />
    <text
      v-if="branch"
      class="edge-branch"
      :class="`is-${branch}`"
      :x="path.labelX"
      :y="path.labelY - 18"
      text-anchor="middle"
    >{{ branch === 'true' ? 'TRUE' : 'FALSE' }}</text>
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
