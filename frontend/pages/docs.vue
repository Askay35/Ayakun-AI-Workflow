<script setup lang="ts">
import type { NodeKind } from '~/types/api'
import { NODE_META } from '~/utils/workflow-graph'

const { t, tm } = useI18n()
useSeoMeta({
  title: () => t('docs.title'),
  description: () => t('docs.description')
})

const NODE_ORDER: NodeKind[] = [
  'web_search',
  'prompt',
  'http_request',
  'if_else',
  'telegram_send',
  'webhook',
  'google_sheets',
  'email',
  'data_transform',
  'sql_query'
]

type NodeGuide = {
  what: string
  how: string[]
  settings: Array<{ name: string; text: string }>
  output: string
  notes: string[]
}

const examples = {
  root: '{{$}}',
  field: '{{$name}}',
  jsonField: '{{$jsonfield}}',
  path: '{{$data[0].field}}',
  dotted: '{{$data.0.field}}',
  variable: '{{field}}',
  total: '{{total}}',
  nestedVar: '{{rows[0].title}}',
  itemPrice: '{{item.field}}',
  loopJson: '{% for item in $data %}\n{{item.label}} — {{item.price}}\n{% endfor %}',
  loopVar: '{% for row in rows %}{{row.title}}{% endfor %}',
  loopTaken: '{% for item in $data %}',
  loopFree: '{% for row in $data %}',
  transformInput: '{\n  "data": [\n    { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x" },\n    { "id": 2, "name": "ETH", "symbol": "ETH", "score": 1, "secret": "y" }\n  ]\n}',
  transformPath: 'data',
  selectFields: 'id, name, score',
  selectOut: '[\n  { "id": 1, "name": "BTC", "score": 3 },\n  { "id": 2, "name": "ETH", "score": 1 }\n]',
  renameMap: 'name=title\nscore=points',
  renameOut: '[\n  { "id": 1, "title": "BTC", "symbol": "BTC", "points": 3, "secret": "x" },\n  { "id": 2, "title": "ETH", "symbol": "ETH", "points": 1, "secret": "y" }\n]',
  setMap: 'status=active\nlabel={{$name}}',
  setOut: '[\n  { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x", "status": "active", "label": "BTC" },\n  { "id": 2, "name": "ETH", "symbol": "ETH", "score": 1, "secret": "y", "status": "active", "label": "ETH" }\n]',
  removeFields: 'secret, symbol',
  removeOut: '[\n  { "id": 1, "name": "BTC", "score": 3 },\n  { "id": 2, "name": "ETH", "score": 1 }\n]',
  filterCondition: '{{$score}} >= 2',
  filterOut: '[\n  { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x" }\n]',
  sortField: 'score',
  sortOut: '[\n  { "id": 2, "name": "ETH", "symbol": "ETH", "score": 1, "secret": "y" },\n  { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x" }\n]',
  map: '{\n  "title": "{{$name}}",\n  "symbol": "{{$symbol}}",\n  "points": "{{$score}}"\n}',
  mapOut: '[\n  { "title": "BTC", "symbol": "BTC", "points": 3 },\n  { "title": "ETH", "symbol": "ETH", "points": 1 }\n]',
  ifScore: '{{$score}} >= 0.8',
  ifStatus: '{{$status}} == "active"'
}

const editorItems = computed(() => tm<string[]>('docs.editorItems'))
const guideOf = (kind: NodeKind) => tm<NodeGuide>(`docs.guides.${kind}`)

const toc = computed(() => [
  { id: 'general', label: t('docs.tocGeneral'), icon: 'i-lucide-book-open', accent: '#6758ee' },
  ...NODE_ORDER.map(kind => ({
    id: kind,
    label: t(`nodes.${kind}.label`),
    icon: NODE_META[kind].icon,
    accent: NODE_META[kind].accent
  }))
])

const activeId = ref('general')
const scrollingTo = ref<string | null>(null)
const tocEl = ref<HTMLElement | null>(null)

const setHash = (id: string) => {
  const next = id === 'general' ? `${location.pathname}${location.search}` : `#${id}`
  if (`${location.pathname}${location.search}${location.hash}` !== `${location.pathname}${location.search}${id === 'general' ? '' : `#${id}`}`) {
    history.replaceState(null, '', next)
  }
}

const go = (id: string) => {
  const el = document.getElementById(`docs-${id}`)
  if (!el) return
  scrollingTo.value = id
  activeId.value = id
  setHash(id)
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  window.setTimeout(() => { if (scrollingTo.value === id) scrollingTo.value = null }, 800)
}

const syncActive = () => {
  if (scrollingTo.value) return
  const marker = 130
  let current = 'general'
  for (const item of toc.value) {
    const el = document.getElementById(`docs-${item.id}`)
    if (el && el.getBoundingClientRect().top <= marker) current = item.id
  }
  if (activeId.value !== current) {
    activeId.value = current
    setHash(current)
  }
}

const revealActiveChip = () => {
  const nav = tocEl.value
  const current = nav?.querySelector<HTMLElement>('.is-active')
  current?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
}

watch(activeId, () => nextTick(revealActiveChip))

onMounted(() => {
  const hash = decodeURIComponent(location.hash.replace(/^#/, ''))
  if (hash && document.getElementById(`docs-${hash}`)) {
    activeId.value = hash
    nextTick(() => document.getElementById(`docs-${hash}`)?.scrollIntoView({ block: 'start' }))
  }
  window.addEventListener('scroll', syncActive, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', syncActive))
</script>

<template>
  <main class="shell docs-page">
    <aside ref="tocEl" class="docs-toc" :aria-label="t('docs.heading')">
      <button
        type="button"
        class="docs-toc-item is-general"
        :class="{ 'is-active': activeId === 'general' }"
        @click="go('general')"
      >
        <span class="docs-toc-icon" style="color:#6758ee;background:#6758ee22">
          <UIcon name="i-lucide-book-open" class="size-4" />
        </span>
        <span>{{ t('docs.tocGeneral') }}</span>
      </button>
      <p class="docs-toc-kicker">{{ t('docs.tocNodes') }}</p>
      <button
        v-for="item in toc.slice(1)"
        :key="item.id"
        type="button"
        class="docs-toc-item"
        :class="{ 'is-active': activeId === item.id }"
        @click="go(item.id)"
      >
        <span class="docs-toc-icon" :style="{ color: item.accent, background: `${item.accent}22` }">
          <UIcon :name="item.icon" class="size-4" />
        </span>
        <span>{{ item.label }}</span>
      </button>
    </aside>

    <div class="docs-article">
      <div id="docs-general" class="docs-section">
        <header class="docs-hero">
          <p class="eyebrow">{{ t('docs.eyebrow') }}</p>
          <h1 class="page-title">{{ t('docs.heading') }}</h1>
          <p class="legal-meta muted">{{ t('docs.lead') }}</p>
        </header>

        <section class="docs-card legal-body">
          <h2>{{ t('docs.editor') }}</h2>
          <ul>
            <li v-for="item in editorItems" :key="item">{{ item }}</li>
          </ul>

          <h2>{{ t('docs.dataTitle') }}</h2>
          <p>{{ t('docs.dataLead') }}</p>
          <ul>
            <li><code>{{ examples.root }}</code> — {{ t('docs.dataRoot') }}</li>
            <li><code>{{ examples.field }}</code> / <code>{{ examples.jsonField }}</code> — {{ t('docs.dataField') }}</li>
            <li><code>{{ examples.path }}</code> — {{ t('docs.dataPath', { dotted: examples.dotted }) }}</li>
          </ul>
          <p>{{ t('docs.dataMissing') }}</p>

          <h2>{{ t('docs.varsTitle') }}</h2>
          <p>{{ t('docs.varsP1', { variable: examples.variable }) }}</p>
          <p>{{ t('docs.varsP2', { total: examples.total }) }}</p>
          <p>{{ t('docs.varsP3', { nested: examples.nestedVar, item: examples.itemPrice }) }}</p>

          <h2>{{ t('docs.loopsTitle') }}</h2>
          <p>{{ t('docs.loopsP1') }}</p>
          <pre><code>{{ examples.loopJson }}</code></pre>
          <p>{{ t('docs.loopsP2') }}</p>
          <pre><code>{{ examples.loopVar }}</code></pre>
          <p>{{ t('docs.loopsP3', { free: examples.loopFree, taken: examples.loopTaken }) }}</p>
        </section>
      </div>

      <article
        v-for="kind in NODE_ORDER"
        :id="`docs-${kind}`"
        :key="kind"
        class="docs-card docs-section legal-body"
      >
        <div class="docs-node-head">
          <span class="docs-node-icon" :style="{ color: NODE_META[kind].accent, background: `${NODE_META[kind].accent}22` }">
            <UIcon :name="NODE_META[kind].icon" class="size-5" />
          </span>
          <div>
            <p class="docs-node-kicker">{{ t(`nodes.${kind}.caption`) }}</p>
            <h2 class="docs-node-title">{{ t(`nodes.${kind}.label`) }}</h2>
          </div>
        </div>

        <h3>{{ t('docs.what') }}</h3>
        <p>{{ guideOf(kind).what }}</p>

        <h3>{{ t('docs.how') }}</h3>
        <ul>
          <li v-for="item in guideOf(kind).how" :key="item">{{ item }}</li>
        </ul>

        <h3>{{ t('docs.settingsTitle') }}</h3>
        <ul>
          <li v-for="item in guideOf(kind).settings" :key="item.name">
            <strong>{{ item.name }}.</strong> {{ item.text }}
          </li>
        </ul>

        <h3>{{ t('docs.outputTitle') }}</h3>
        <p>{{ guideOf(kind).output }}</p>

        <h3>{{ t('docs.notesTitle') }}</h3>
        <ul>
          <li v-for="item in guideOf(kind).notes" :key="item">{{ item }}</li>
        </ul>

        <template v-if="kind === 'if_else'">
          <h3>{{ t('docs.ifTitle') }}</h3>
          <p>{{ t('docs.ifP', { a: examples.ifScore, b: examples.ifStatus }) }}</p>
          <p>{{ t('docs.ifOps') }}</p>
        </template>

        <template v-if="kind === 'data_transform'">
          <p>{{ t('docs.transformP2', { path: examples.transformPath }) }}</p>
          <pre><code>{{ examples.transformInput }}</code></pre>

          <h3>{{ t('docs.selectTitle') }}</h3>
          <p>{{ t('docs.selectP') }}</p>
          <p>{{ t('docs.fields') }}: <code>{{ examples.selectFields }}</code></p>
          <pre><code>{{ examples.selectOut }}</code></pre>

          <h3>{{ t('docs.renameTitle') }}</h3>
          <p>{{ t('docs.renameP') }}</p>
          <pre><code>{{ examples.renameMap }}</code></pre>
          <pre><code>{{ examples.renameOut }}</code></pre>

          <h3>{{ t('docs.setTitle') }}</h3>
          <p>{{ t('docs.setP') }}</p>
          <pre><code>{{ examples.setMap }}</code></pre>
          <pre><code>{{ examples.setOut }}</code></pre>

          <h3>{{ t('docs.removeTitle') }}</h3>
          <p>{{ t('docs.removeP') }}</p>
          <p>{{ t('docs.fields') }}: <code>{{ examples.removeFields }}</code></p>
          <pre><code>{{ examples.removeOut }}</code></pre>

          <h3>{{ t('docs.filterTitle') }}</h3>
          <p>{{ t('docs.filterP') }}</p>
          <p>{{ t('docs.condition') }}: <code>{{ examples.filterCondition }}</code></p>
          <pre><code>{{ examples.filterOut }}</code></pre>

          <h3>{{ t('docs.sortTitle') }}</h3>
          <p>{{ t('docs.sortP') }}</p>
          <p>{{ t('docs.sortField') }}: <code>{{ examples.sortField }}</code>, {{ t('docs.sortDir') }}</p>
          <pre><code>{{ examples.sortOut }}</code></pre>

          <h3>{{ t('docs.mapTitle') }}</h3>
          <p>{{ t('docs.mapP') }}</p>
          <pre><code>{{ examples.map }}</code></pre>
          <pre><code>{{ examples.mapOut }}</code></pre>
          <p>{{ t('docs.mapAfter') }}</p>
        </template>
      </article>
    </div>
  </main>
</template>
