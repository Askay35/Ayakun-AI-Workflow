<template>
  <main class="landing">
    <section class="hero">
      <div class="shell hero-grid">
        <div class="reveal">
          <p class="eyebrow">{{ t('landing.eyebrow') }}</p>
          <h1>{{ t('landing.heroTitleBefore') }}<br><span class="hero-shine">{{ t('landing.heroTitleAccent') }}</span></h1>
          <p class="hero-copy">{{ t('landing.heroCopy') }}</p>
          <div class="hero-actions">
            <UButton to="/login" size="xl" :label="t('landing.startFree')" trailing-icon="i-lucide-arrow-right" />
            <UButton to="/#examples" size="xl" :label="t('landing.seeExamples')" class="text-white!" color="neutral" variant="outline" />
          </div>
          <div class="trust-row">
            <span><UIcon name="i-lucide-check-circle-2" /> {{ t('landing.trustNoCode') }}</span>
            <span><UIcon name="i-lucide-check-circle-2" /> {{ t('landing.trustPrice') }}</span>
            <span><UIcon name="i-lucide-check-circle-2" /> {{ t('landing.trustCredits') }}</span>
          </div>
        </div>
        <LandingCanvas class="reveal" style="animation-delay: 140ms" />
      </div>
    </section>

    <div class="node-rail" aria-hidden="true">
      <div class="node-rail-track">
        <span v-for="(label, index) in railLoop" :key="`${label}-${index}`">{{ label }}</span>
      </div>
    </div>

    <section class="unique-strip">
      <div class="shell unique-grid">
        <article v-for="(item, index) in unique" :key="item.title" class="unique-card" :style="{ animationDelay: `${index * 80}ms` }">
          <span class="unique-icon"><UIcon :name="item.icon" class="size-5" /></span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.text }}</p>
        </article>
      </div>
    </section>

    <section id="features" class="section alt">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('landing.featuresEyebrow') }}</p>
          <h2>{{ t('landing.featuresTitle') }}</h2>
          <p>{{ t('landing.featuresLead') }}</p>
        </div>
        <div class="blocks-grid landing-bento">
          <article v-for="card in blocks" :key="card.title" class="feature-card">
            <span class="feature-number">{{ card.number }}</span>
            <span class="feature-icon" :style="{ color: card.accent, background: `${card.accent}22` }">
              <UIcon :name="card.icon" class="size-5" />
            </span>
            <h3>{{ card.title }}</h3>
            <p>{{ card.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="examples" class="section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('landing.examplesEyebrow') }}</p>
          <h2>{{ t('landing.examplesTitle') }}</h2>
          <p>{{ t('landing.examplesLead') }}</p>
        </div>
        <div class="examples-grid">
          <article v-for="example in examples" :key="example.title" class="example-card">
            <div class="example-top">
              <span class="example-tag">{{ example.tag }}</span>
              <span class="example-schedule">{{ example.schedule }}</span>
            </div>
            <h3>{{ example.title }}</h3>
            <p>{{ example.text }}</p>
            <div class="example-chain">
              <template v-for="(step, index) in example.chain" :key="`${example.title}-${step}`">
                <span class="example-step" :style="{ '--step-accent': example.accents[index] }">
                  <UIcon :name="example.icons[index]" class="size-3.5" />
                  {{ step }}
                </span>
                <UIcon v-if="index < example.chain.length - 1" name="i-lucide-arrow-right" class="example-arrow" />
              </template>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section id="how" class="section how-section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('landing.howEyebrow') }}</p>
          <h2>{{ t('landing.howTitle') }}</h2>
          <p>{{ t('landing.howLead') }}</p>
        </div>
        <LandingShots />
        <div class="build-track">
          <article v-for="(step, index) in steps" :key="step.title" class="build-step">
            <div class="build-visual" :class="`is-${step.id}`">
              <span v-for="dot in step.icons.length" :key="dot" class="build-chip" :style="{ animationDelay: `${index * 180 + dot * 90}ms` }">
                <UIcon :name="step.icons[dot - 1]" class="size-3.5" />
              </span>
            </div>
            <b>{{ step.number }}</b>
            <h3>{{ step.title }}</h3>
            <p>{{ step.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section audience">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">{{ t('landing.audienceEyebrow') }}</p>
          <h2>{{ t('landing.audienceTitle') }}</h2>
        </div>
        <div class="audience-grid audience-grid-wide">
          <article v-for="item in audience" :key="item.title" class="audience-card">
            <span class="audience-icon"><UIcon :name="item.icon" class="size-6" /></span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
            <p class="audience-example">{{ item.example }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section pt-0!">
      <div class="shell">
        <div class="cta-band">
          <div>
            <p class="eyebrow !mb-3 text-[#3d4a12]!">{{ t('landing.ctaEyebrow') }}</p>
            <h2>{{ t('landing.ctaTitle') }}</h2>
          </div>
          <UButton to="/login" size="xl" color="neutral" :label="t('landing.ctaButton')" trailing-icon="i-lucide-arrow-up-right" />
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

const uniqueIcons = ['i-lucide-mouse-pointer-click', 'i-lucide-unplug', 'i-lucide-calendar-clock', 'i-lucide-wallet']
const unique = computed(() => tm<Array<{ title: string; text: string }>>('landing.unique').map((item, index) => ({
  ...item,
  icon: uniqueIcons[index]
})))

const blockMeta = [
  { icon: 'i-lucide-search', accent: '#2bbf8e' },
  { icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  { icon: 'i-lucide-globe', accent: '#f59e0b' },
  { icon: 'i-lucide-git-branch', accent: '#e8b84a' },
  { icon: 'i-lucide-send', accent: '#2aa8e0' },
  { icon: 'i-lucide-webhook', accent: '#f472b6' },
  { icon: 'i-lucide-table', accent: '#22c55e' },
  { icon: 'i-lucide-mail', accent: '#ea4335' },
  { icon: 'i-lucide-replace', accent: '#38bdf8' },
  { icon: 'i-lucide-database', accent: '#6366f1' }
]
const blocks = computed(() => tm<Array<{ number: string; title: string; text: string }>>('landing.blocks').map((item, index) => ({
  ...item,
  ...blockMeta[index]
})))

const exampleMeta = [
  { icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-send'], accents: ['#2bbf8e', '#8b7cff', '#2aa8e0'] },
  { icons: ['i-lucide-globe', 'i-lucide-git-branch', 'i-lucide-send'], accents: ['#f59e0b', '#e8b84a', '#2aa8e0'] },
  { icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-send'], accents: ['#2bbf8e', '#8b7cff', '#2aa8e0'] },
  { icons: ['i-lucide-webhook', 'i-lucide-table', 'i-lucide-send'], accents: ['#f472b6', '#22c55e', '#2aa8e0'] },
  { icons: ['i-lucide-webhook', 'i-lucide-sparkles', 'i-lucide-mail'], accents: ['#f472b6', '#8b7cff', '#ea4335'] },
  { icons: ['i-lucide-database', 'i-lucide-git-branch', 'i-lucide-mail'], accents: ['#6366f1', '#e8b84a', '#ea4335'] }
]
const examples = computed(() => tm<Array<{ tag: string; schedule: string; title: string; text: string; chain: string[] }>>('landing.examples').map((item, index) => ({
  ...item,
  ...exampleMeta[index]
})))

const stepMeta = [
  { id: 'assemble', icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-mail', 'i-lucide-database', 'i-lucide-send'] },
  { id: 'describe', icons: ['i-lucide-type', 'i-lucide-braces', 'i-lucide-git-branch'] },
  { id: 'run', icons: ['i-lucide-play', 'i-lucide-clock', 'i-lucide-mail'] }
]
const steps = computed(() => tm<Array<{ number: string; title: string; text: string }>>('landing.steps').map((item, index) => ({
  ...item,
  ...stepMeta[index]
})))

const railKinds = [
  'web_search',
  'prompt',
  'http_request',
  'if_else',
  'telegram_send',
  'webhook',
  'google_sheets',
  'email',
  'loop',
  'delay',
  'image_generation',
  'audio_transcription'
] as const
const rail = computed(() => railKinds.map(kind => t(`nodes.${kind}.label`)))
const railLoop = computed(() => [...rail.value, ...rail.value])

const audienceIcons = ['i-lucide-briefcase', 'i-lucide-user-round-search', 'i-lucide-pen-line', 'i-lucide-trending-up', 'i-lucide-building-2', 'i-lucide-code-2']
const audience = computed(() => tm<Array<{ title: string; text: string; example: string }>>('landing.audience').map((item, index) => ({
  ...item,
  icon: audienceIcons[index]
})))
</script>
