<script setup lang="ts">
export interface AdminChartSeries {
  key: string
  label: string
  color: string
  values: number[]
}

const props = withDefaults(defineProps<{
  type?: 'bar' | 'line'
  labels: string[]
  /** Полные подписи периодов для подсказки; по умолчанию — labels. */
  titles?: string[]
  series: AdminChartSeries[]
  format?: (value: number) => string
  /** Дополнительные строки подсказки для точки по индексу. */
  details?: (index: number) => string[]
  height?: number
}>(), {
  type: 'bar',
  format: (value: number) => value.toLocaleString('ru-RU'),
  titles: undefined,
  details: undefined,
  height: 240
})

const PAD = { top: 12, right: 12, bottom: 28, left: 52 }
const root = ref<HTMLElement>()
const width = ref(640)
const hover = ref<number | null>(null)
let observer: ResizeObserver | undefined

onMounted(() => {
  if (!root.value) return
  width.value = root.value.clientWidth || width.value
  observer = new ResizeObserver(([entry]) => {
    if (entry) width.value = Math.max(240, Math.round(entry.contentRect.width))
  })
  observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

const count = computed(() => props.labels.length)
const plotWidth = computed(() => width.value - PAD.left - PAD.right)
const plotHeight = computed(() => props.height - PAD.top - PAD.bottom)
const slot = computed(() => plotWidth.value / Math.max(count.value, 1))

const totals = computed(() => props.labels.map((_, index) =>
  props.series.reduce((sum, item) => sum + (item.values[index] || 0), 0)
))
const niceStep = (raw: number) => {
  const power = 10 ** Math.floor(Math.log10(raw))
  const unit = raw / power
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * power
}
const scale = computed(() => {
  const peak = props.type === 'bar'
    ? Math.max(0, ...totals.value)
    : Math.max(0, ...props.series.flatMap(item => item.values))
  if (!peak) return { max: 1, ticks: [0] }
  const step = niceStep(peak / 4)
  const max = Math.ceil(peak / step) * step
  return { max, ticks: Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step) }
})
const y = (value: number) => PAD.top + plotHeight.value - (value / scale.value.max) * plotHeight.value
const x = (index: number) => PAD.left + slot.value * index + slot.value / 2

const barWidth = computed(() => Math.max(2, Math.min(24, slot.value * 0.62)))
const barRadius = computed(() => Math.min(4, barWidth.value / 2))
/** Столбик со скруглённым верхом и прямым основанием. */
const barPath = (cx: number, top: number, bottom: number, rounded: boolean) => {
  const half = barWidth.value / 2
  const height = bottom - top
  if (height <= 0) return ''
  const r = rounded ? Math.min(barRadius.value, height) : 0
  return `M${cx - half},${bottom}V${top + r}${r ? `Q${cx - half},${top} ${cx - half + r},${top}` : ''}`
    + `H${cx + half - r}${r ? `Q${cx + half},${top} ${cx + half},${top + r}` : ''}V${bottom}Z`
}
const bars = computed(() => props.labels.flatMap((_, index) => {
  let base = 0
  const visible = props.series.filter(item => (item.values[index] || 0) > 0)
  return visible.map((item, order) => {
    const value = item.values[index] || 0
    const bottom = y(base) - (order ? 1 : 0)
    base += value
    const top = y(base) + (order < visible.length - 1 ? 1 : 0)
    return { key: `${item.key}-${index}`, color: item.color, d: barPath(x(index), top, bottom, order === visible.length - 1) }
  })
}))
const lines = computed(() => props.series.map(item => {
  const points = item.values.map((value, index) => `${x(index)},${y(value || 0)}`)
  const baseline = y(0)
  return {
    key: item.key,
    color: item.color,
    line: `M${points.join('L')}`,
    area: `M${x(0)},${baseline}L${points.join('L')}L${x(item.values.length - 1)},${baseline}Z`
  }
}))

const labelEvery = computed(() => Math.max(1, Math.ceil(count.value / Math.max(2, Math.floor(plotWidth.value / 64)))))
const tooltip = computed(() => {
  if (hover.value == null) return null
  const index = hover.value
  const left = x(index)
  return {
    title: props.titles?.[index] ?? props.labels[index],
    rows: props.series.map(item => ({ label: item.label, color: item.color, value: props.format(item.values[index] || 0) })),
    total: props.type === 'bar' && props.series.length > 1 ? props.format(totals.value[index] || 0) : null,
    extra: props.details?.(index) || [],
    style: left > width.value / 2
      ? { right: `${width.value - left + 14}px` }
      : { left: `${left + 14}px` }
  }
})
const onMove = (event: MouseEvent) => {
  const rect = (event.currentTarget as SVGElement).getBoundingClientRect()
  const index = Math.floor((event.clientX - rect.left - PAD.left) / slot.value)
  hover.value = index >= 0 && index < count.value ? index : null
}
</script>

<template>
  <div ref="root" class="admin-chart">
    <div v-if="series.length > 1" class="admin-chart-legend">
      <span v-for="item in series" :key="item.key">
        <i :style="{ background: item.color }" />{{ item.label }}
      </span>
    </div>
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      :width="width"
      :height="height"
      role="img"
      @mousemove="onMove"
      @mouseleave="hover = null"
    >
      <g class="admin-chart-grid">
        <template v-for="tick in scale.ticks" :key="tick">
          <line :x1="PAD.left" :x2="width - PAD.right" :y1="y(tick)" :y2="y(tick)" />
          <text :x="PAD.left - 8" :y="y(tick)" text-anchor="end" dominant-baseline="middle">{{ format(tick) }}</text>
        </template>
      </g>
      <rect
        v-if="hover != null"
        class="admin-chart-hover"
        :x="PAD.left + slot * hover"
        :y="PAD.top"
        :width="slot"
        :height="plotHeight"
        rx="6"
      />
      <template v-if="type === 'bar'">
        <path v-for="bar in bars" :key="bar.key" :d="bar.d" :fill="bar.color" />
      </template>
      <template v-else>
        <g v-for="item in lines" :key="item.key">
          <path :d="item.area" :fill="item.color" fill-opacity="0.1" />
          <path :d="item.line" :stroke="item.color" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
        </g>
        <template v-if="hover != null">
          <circle
            v-for="item in series"
            :key="item.key"
            :cx="x(hover)"
            :cy="y(item.values[hover] || 0)"
            r="4.5"
            :fill="item.color"
            stroke="#fff"
            stroke-width="2"
          />
        </template>
      </template>
      <g class="admin-chart-axis">
        <text
          v-for="(label, index) in labels"
          v-show="(count - 1 - index) % labelEvery === 0"
          :key="index"
          :x="x(index)"
          :y="height - 8"
          text-anchor="middle"
        >{{ label }}</text>
      </g>
    </svg>
    <div v-if="tooltip" class="admin-chart-tooltip" :style="tooltip.style">
      <p class="admin-chart-tooltip-title">{{ tooltip.title }}</p>
      <p v-for="row in tooltip.rows" :key="row.label" class="admin-chart-tooltip-row">
        <span><i :style="{ background: row.color }" />{{ row.label }}</span>
        <strong>{{ row.value }}</strong>
      </p>
      <p v-if="tooltip.total" class="admin-chart-tooltip-row">
        <span>Всего</span><strong>{{ tooltip.total }}</strong>
      </p>
      <p v-for="line in tooltip.extra" :key="line" class="admin-chart-tooltip-extra">{{ line }}</p>
    </div>
  </div>
</template>
