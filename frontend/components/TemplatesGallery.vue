<script setup lang="ts">
import type { WorkflowTemplate } from '~/types/api'
import { NODE_META } from '~/utils/workflow-graph'

const props = defineProps<{
  templates: WorkflowTemplate[]
  limit?: number
  filters?: boolean
}>()

const { t, locale } = useI18n()
const CATEGORIES = ['all', 'content', 'sales', 'ops', 'monitoring', 'dev', 'media'] as const
const category = ref<(typeof CATEGORIES)[number]>('all')
const query = ref('')

const title = (item: WorkflowTemplate) => (locale.value === 'en' ? item.name_en : item.name)
const text = (item: WorkflowTemplate) => (locale.value === 'en' ? item.description_en : item.description)
const visible = computed(() => {
  const needle = query.value.trim().toLowerCase()
  const list = props.templates.filter(item => (
    (category.value === 'all' || item.category === category.value)
    && (!needle || `${title(item)} ${text(item)} ${item.steps.map(step => step.label).join(' ')}`.toLowerCase().includes(needle))
  ))
  return props.limit ? list.slice(0, props.limit) : list
})
const counts = computed(() => Object.fromEntries(CATEGORIES.map(key => [
  key,
  key === 'all' ? props.templates.length : props.templates.filter(item => item.category === key).length
])))
</script>

<template>
  <div>
    <div v-if="filters" class="templates-toolbar">
      <div class="cat-tabs templates-tabs" role="tablist">
        <button
          v-for="key in CATEGORIES"
          :key="key"
          type="button"
          role="tab"
          class="cat-tab"
          :class="{ active: category === key }"
          :aria-selected="category === key"
          @click="category = key"
        >
          {{ t(`templates.categories.${key}`) }} <span class="templates-count">{{ counts[key] }}</span>
        </button>
      </div>
      <UInput v-model="query" icon="i-lucide-search" :placeholder="t('templates.search')" class="templates-search" />
    </div>
    <div class="templates-grid">
      <NuxtLink v-for="item in visible" :key="item.slug" :to="`/templates/${item.slug}`" class="template-card">
        <div class="template-card-top">
          <span class="example-tag">{{ t(`templates.categories.${item.category}`) }}</span>
          <span class="template-steps-count">{{ t('templates.steps', { n: item.steps.length }) }}</span>
        </div>
        <h3>{{ title(item) }}</h3>
        <p>{{ text(item) }}</p>
        <div class="template-chain">
          <template v-for="(step, index) in item.steps" :key="`${item.slug}-${index}`">
            <span
              class="template-chain-icon"
              :title="step.label"
              :style="{ color: NODE_META[step.type]?.accent, background: `${NODE_META[step.type]?.accent}1a` }"
            >
              <UIcon :name="NODE_META[step.type]?.icon || 'i-lucide-box'" class="size-3.5" />
            </span>
            <UIcon v-if="index < item.steps.length - 1" name="i-lucide-chevron-right" class="template-chain-arrow" />
          </template>
        </div>
        <span class="template-card-cta">
          {{ t('templates.use') }} <UIcon name="i-lucide-arrow-right" class="size-4" />
        </span>
      </NuxtLink>
    </div>
    <p v-if="!visible.length" class="py-10 text-center muted">{{ t('templates.empty') }}</p>
  </div>
</template>
