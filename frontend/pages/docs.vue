<script setup lang="ts">
const { t, tm } = useI18n()
useSeoMeta({
  title: () => t('docs.title'),
  description: () => t('docs.description')
})

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

const fill = (text: string, vars: Record<string, string>) => (
  text.replace(/\{(\w+)\}/g, (_, key: string) => (
    Object.prototype.hasOwnProperty.call(vars, key) ? vars[key] : `{${key}}`
  ))
)

const editorItems = computed(() => tm<string[]>('docs.editorItems'))
const tgItems = computed(() => tm<string[]>('docs.tgItems').map(item => fill(item, { root: examples.root })))
const emailItems = computed(() => tm<string[]>('docs.emailItems'))
</script>

<template>
  <main class="shell legal-page">
    <div class="legal-card reveal">
      <p class="eyebrow">{{ t('docs.eyebrow') }}</p>
      <h1 class="page-title">{{ t('docs.heading') }}</h1>
      <p class="legal-meta muted">{{ t('docs.lead') }}</p>

      <div class="legal-body">
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

        <h2>{{ t('docs.tgTitle') }}</h2>
        <ul>
          <li v-for="item in tgItems" :key="item">{{ item }}</li>
        </ul>

        <h2>{{ t('docs.emailTitle') }}</h2>
        <ul>
          <li v-for="item in emailItems" :key="item">{{ item }}</li>
        </ul>

        <h2>{{ t('docs.transformTitle') }}</h2>
        <p>{{ t('docs.transformP1', { path: examples.transformPath }) }}</p>
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

        <h2>{{ t('docs.ifTitle') }}</h2>
        <p>{{ t('docs.ifP', { a: examples.ifScore, b: examples.ifStatus }) }}</p>
      </div>
    </div>
  </main>
</template>
