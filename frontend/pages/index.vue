<template>
  <main class="landing">
    <section class="hero">
      <div class="shell hero-inner">
        <p class="hero-badge reveal"><UIcon name="i-lucide-sparkles" class="size-4" /> {{ t('landing.eyebrow') }}</p>
        <h1 class="reveal" style="animation-delay: 60ms">{{ t('landing.heroTitleBefore') }} <span class="hero-accent">{{ t('landing.heroTitleAccent') }}</span></h1>
        <p class="hero-copy reveal" style="animation-delay: 120ms">{{ t('landing.heroCopy') }}</p>
        <div class="hero-actions reveal" style="animation-delay: 180ms">
          <NuxtLink to="/login" class="site-button large">{{ t('landing.startFree') }} <UIcon name="i-lucide-arrow-right" /></NuxtLink>
          <NuxtLink to="/#examples" class="site-button large secondary">{{ t('landing.seeExamples') }}</NuxtLink>
        </div>
        <div class="trust-row reveal" style="animation-delay: 220ms">
          <span><UIcon name="i-lucide-check" /> {{ t('landing.trustNoCode') }}</span>
          <span><UIcon name="i-lucide-check" /> {{ t('landing.trustPrice') }}</span>
          <span><UIcon name="i-lucide-check" /> {{ t('landing.trustTokens') }}</span>
        </div>
      </div>
      <div class="shell hero-visual reveal" style="animation-delay: 280ms">
        <LandingCanvas />
      </div>
      <div class="shell">
        <div class="stats">
          <div v-for="item in stats" :key="item.label" class="stat">
            <b>{{ item.value }}</b>
            <span>{{ item.label }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="rail">
      <div class="shell">
        <p class="rail-title">{{ t('landing.railTitle') }}</p>
        <div class="rail-chips">
          <span v-for="item in rail" :key="item.label" class="rail-chip">
            <UIcon :name="item.icon" class="size-4" :style="{ color: item.accent }" />
            {{ item.label }}
          </span>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('landing.uniqueEyebrow') }}</p>
          <h2>{{ t('landing.uniqueTitle') }}</h2>
        </div>
        <div class="unique-grid">
          <article v-for="item in unique" :key="item.title" class="unique-card">
            <span class="tile"><UIcon :name="item.icon" class="size-5" /></span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="features" class="section alt">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('landing.featuresEyebrow') }}</p>
          <h2>{{ t('landing.featuresTitle') }}</h2>
          <p>{{ t('landing.featuresLead') }}</p>
        </div>
        <div class="cat-tabs" role="tablist">
          <button
            v-for="cat in categories"
            :key="cat"
            type="button"
            role="tab"
            class="cat-tab"
            :class="{ active: activeCat === cat }"
            :aria-selected="activeCat === cat"
            @click="activeCat = cat"
          >
            {{ t(`landing.categories.${cat}`) }}
          </button>
        </div>
        <div class="blocks-grid">
          <article v-for="card in visibleBlocks" :key="card.title" class="block-card">
            <span class="block-icon" :style="{ color: card.accent, background: `${card.accent}1f` }">
              <UIcon :name="card.icon" class="size-5" />
            </span>
            <h3>{{ card.title }}</h3>
            <p>{{ card.text }}</p>
          </article>
        </div>
        <div v-if="activeCat === 'all'" class="blocks-more">
          <button type="button" class="site-button secondary" @click="expanded = !expanded">
            {{ expanded ? t('landing.showLess') : t('landing.showMore') }}
            <UIcon :name="expanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
          </button>
        </div>
      </div>
    </section>

    <section id="examples" class="section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('templates.landingEyebrow') }}</p>
          <h2>{{ t('templates.landingTitle') }}</h2>
          <p>{{ t('templates.landingLead') }}</p>
        </div>
        <TemplatesGallery :templates="featuredTemplates" />
        <div class="blocks-more">
          <NuxtLink to="/templates" class="site-button secondary">
            {{ t('templates.landingAll', { n: templates?.length || 30 }) }}
            <UIcon name="i-lucide-arrow-right" />
          </NuxtLink>
        </div>
      </div>
    </section>

    <section id="how" class="section alt">
      <div class="shell">
        <div class="section-heading center">
          <p class="eyebrow">{{ t('landing.howEyebrow') }}</p>
          <h2>{{ t('landing.howTitle') }}</h2>
          <p>{{ t('landing.howLead') }}</p>
        </div>
        <div class="steps-grid">
          <article v-for="step in steps" :key="step.title" class="step-card">
            <span class="step-number">{{ step.number }}</span>
            <h3>{{ step.title }}</h3>
            <p>{{ step.text }}</p>
          </article>
        </div>
        <LandingShots />
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <div class="section-heading center">
          <p class="eyebrow">{{ t('landing.audienceEyebrow') }}</p>
          <h2>{{ t('landing.audienceTitle') }}</h2>
        </div>
        <div class="audience-grid">
          <article v-for="item in audience" :key="item.title" class="audience-card">
            <span class="tile"><UIcon :name="item.icon" class="size-5" /></span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
            <p class="audience-example">{{ item.example }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section alt">
      <div class="shell faq">
        <div class="section-heading center">
          <p class="eyebrow">{{ t('landing.faqEyebrow') }}</p>
          <h2>{{ t('landing.faqTitle') }}</h2>
        </div>
        <div class="faq-list">
          <details v-for="item in faq" :key="item.q" class="faq-item">
            <summary>
              {{ item.q }}
              <UIcon name="i-lucide-plus" class="faq-icon size-5" />
            </summary>
            <p>{{ item.a }}</p>
          </details>
        </div>
      </div>
    </section>

    <section class="section cta-section">
      <div class="shell">
        <div class="cta-band">
          <p class="cta-eyebrow">{{ t('landing.ctaEyebrow') }}</p>
          <h2>{{ t('landing.ctaTitle') }}</h2>
          <p>{{ t('landing.ctaLead') }}</p>
          <NuxtLink to="/login" class="cta-button">{{ t('landing.ctaButton') }} <UIcon name="i-lucide-arrow-right" /></NuxtLink>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
const { t, tm } = useI18n()
useSeoMeta({
  title: () => t('meta.siteTitle'),
  description: () => t('meta.siteDescription')
})

const stats = computed(() => tm<Array<{ value: string; label: string }>>('landing.stats'))

const uniqueIcons = ['i-lucide-layout-dashboard', 'i-lucide-bot', 'i-lucide-calendar-clock', 'i-lucide-wallet']
const unique = computed(() => tm<Array<{ title: string; text: string }>>('landing.unique').map((item, index) => ({
  ...item,
  icon: uniqueIcons[index]
})))

// Порядок совпадает с landing.blocks в i18n.
const blockMeta = [
  { icon: 'i-lucide-search', accent: '#12a67a', cat: 'data' },
  { icon: 'i-lucide-sparkles', accent: '#6d4aff', cat: 'ai' },
  { icon: 'i-lucide-globe', accent: '#e58a0b', cat: 'data' },
  { icon: 'i-lucide-git-branch', accent: '#c99a12', cat: 'logic' },
  { icon: 'i-lucide-send', accent: '#229ed9', cat: 'delivery' },
  { icon: 'i-lucide-webhook', accent: '#e0439b', cat: 'delivery' },
  { icon: 'i-lucide-table', accent: '#1f9d55', cat: 'data' },
  { icon: 'i-lucide-mail', accent: '#e03c2e', cat: 'delivery' },
  { icon: 'i-lucide-replace', accent: '#0e8fd6', cat: 'logic' },
  { icon: 'i-lucide-database', accent: '#4f56e0', cat: 'data' },
  { icon: 'i-lucide-repeat', accent: '#ea6a0c', cat: 'logic' },
  { icon: 'i-lucide-timer', accent: '#64748b', cat: 'logic' },
  { icon: 'i-lucide-hard-drive', accent: '#d9a400', cat: 'data' },
  { icon: 'i-lucide-image-plus', accent: '#d6338a', cat: 'ai' },
  { icon: 'i-lucide-image', accent: '#e5484d', cat: 'data' },
  { icon: 'i-lucide-scan-eye', accent: '#7c5cff', cat: 'ai' },
  { icon: 'i-lucide-audio-lines', accent: '#0d9488', cat: 'ai' },
  { icon: 'i-simple-icons-slack', accent: '#611f69', cat: 'delivery' },
  { icon: 'i-simple-icons-trello', accent: '#0079bf', cat: 'delivery' },
  { icon: 'i-simple-icons-jira', accent: '#0052cc', cat: 'delivery' },
  { icon: 'i-simple-icons-microsoftexcel', accent: '#107c41', cat: 'data' },
  { icon: 'i-lucide-file-up', accent: '#64748b', cat: 'data' },
  { icon: 'i-lucide-table-2', accent: '#0f9d58', cat: 'data' },
  { icon: 'i-simple-icons-linkedin', accent: '#0a66c2', cat: 'delivery' },
  { icon: 'i-lucide-building-2', accent: '#0067ff', cat: 'delivery' }
]
const blocks = computed(() => tm<Array<{ title: string; text: string }>>('landing.blocks').map((item, index) => ({
  ...item,
  ...(blockMeta[index] || { icon: 'i-lucide-box', accent: '#6d4aff', cat: 'logic' })
})))

const categories = ['all', 'data', 'ai', 'logic', 'delivery'] as const
const activeCat = ref<(typeof categories)[number]>('all')
const expanded = ref(false)
const PREVIEW_COUNT = 8
const visibleBlocks = computed(() => {
  const list = activeCat.value === 'all' ? blocks.value : blocks.value.filter(block => block.cat === activeCat.value)
  return activeCat.value === 'all' && !expanded.value ? list.slice(0, PREVIEW_COUNT) : list
})

const api = useApi()
const { data: templates } = await useAsyncData('landing-templates', () => api.templates.list().catch(() => []))
const FEATURED_TEMPLATES = [
  'news-digest-telegram',
  'lead-scoring-reply',
  'bug-report-to-jira',
  'weekly-report-to-disk',
  'receipt-to-excel',
  'client-profile-merge'
]
const featuredTemplates = computed(() => FEATURED_TEMPLATES
  .map(slug => templates.value?.find(item => item.slug === slug))
  .filter(item => item !== undefined))

const steps = computed(() => tm<Array<{ number: string; title: string; text: string }>>('landing.steps'))

const railKinds = [
  { kind: 'web_search', icon: 'i-lucide-search', accent: '#12a67a' },
  { kind: 'prompt', icon: 'i-lucide-sparkles', accent: '#6d4aff' },
  { kind: 'telegram_send', icon: 'i-lucide-send', accent: '#229ed9' },
  { kind: 'google_sheets', icon: 'i-lucide-table', accent: '#1f9d55' },
  { kind: 'email', icon: 'i-lucide-mail', accent: '#e03c2e' },
  { kind: 'webhook', icon: 'i-lucide-webhook', accent: '#e0439b' },
  { kind: 'http_request', icon: 'i-lucide-globe', accent: '#e58a0b' },
  { kind: 'sql_query', icon: 'i-lucide-database', accent: '#4f56e0' },
  { kind: 'yandex_disk', icon: 'i-lucide-hard-drive', accent: '#d9a400' },
  { kind: 'slack', icon: 'i-simple-icons-slack', accent: '#611f69' },
  { kind: 'trello', icon: 'i-simple-icons-trello', accent: '#0079bf' },
  { kind: 'jira', icon: 'i-simple-icons-jira', accent: '#0052cc' },
  { kind: 'excel', icon: 'i-simple-icons-microsoftexcel', accent: '#107c41' },
  { kind: 'linkedin', icon: 'i-simple-icons-linkedin', accent: '#0a66c2' },
  { kind: 'spreadsheet', icon: 'i-lucide-table-2', accent: '#0f9d58' },
  { kind: 'image_generation', icon: 'i-lucide-image-plus', accent: '#d6338a' },
  { kind: 'audio_transcription', icon: 'i-lucide-audio-lines', accent: '#0d9488' },
  { kind: 'bitrix24', icon: 'i-lucide-building-2', accent: '#0067ff' }
]
const rail = computed(() => railKinds.map(item => ({ ...item, label: t(`nodes.${item.kind}.label`) })))

const audienceIcons = ['i-lucide-briefcase', 'i-lucide-user-round-search', 'i-lucide-pen-line', 'i-lucide-trending-up', 'i-lucide-building-2', 'i-lucide-users']
const audience = computed(() => tm<Array<{ title: string; text: string; example: string }>>('landing.audience').map((item, index) => ({
  ...item,
  icon: audienceIcons[index]
})))

const faq = computed(() => tm<Array<{ q: string; a: string }>>('landing.faq'))
</script>
