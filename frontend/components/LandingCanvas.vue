<script setup lang="ts">
const { t, tm } = useI18n()

const chain = computed(() => [
  { id: 'search', label: t('landing.canvas.searchLabel'), caption: t('landing.canvas.searchCaption'), icon: 'i-lucide-search', accent: '#12a67a' },
  { id: 'prompt', label: t('landing.canvas.promptLabel'), caption: t('landing.canvas.promptCaption'), icon: 'i-lucide-sparkles', accent: '#6d4aff' },
  { id: 'telegram', label: t('landing.canvas.telegramLabel'), caption: t('landing.canvas.telegramCaption'), icon: 'i-lucide-send', accent: '#229ed9' }
])

const logs = computed(() => tm<string[]>('landing.canvas.logs'))

const active = ref(0)
const running = ref(true)
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    active.value = chain.value.length - 1
    running.value = false
    return
  }
  timer = setInterval(() => {
    active.value = (active.value + 1) % chain.value.length
  }, 2200)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="landing-canvas" aria-hidden="true">
    <div class="landing-canvas-bar">
      <span class="landing-dots"><i /><i /><i /></span>
      <div class="landing-canvas-title">
        <b>{{ t('landing.canvas.name') }}</b>
        <span>{{ t('landing.canvas.schedule') }}</span>
      </div>
      <span class="landing-run-pill" :class="{ 'is-live': running }">
        <i />
        {{ running ? t('landing.canvas.running') : t('landing.canvas.done') }}
      </span>
    </div>

    <div class="landing-stage">
      <template v-for="(node, index) in chain" :key="node.id">
        <div v-if="index > 0" class="landing-link" :class="{ 'is-done': active >= index }" />
        <article
          class="landing-node"
          :class="{ 'is-active': active === index, 'is-done': active > index }"
          :style="{ '--node-accent': node.accent }"
        >
          <span class="landing-node-icon"><UIcon :name="node.icon" class="size-5" /></span>
          <div class="min-w-0">
            <p class="landing-node-label">{{ node.label }}</p>
            <p class="landing-node-caption">{{ node.caption }}</p>
          </div>
          <span class="landing-node-state">
            <UIcon v-if="active > index" name="i-lucide-check" class="size-3.5" />
            <i v-else-if="active === index" />
          </span>
        </article>
      </template>
    </div>

    <div class="landing-foot">
      <div class="landing-log">
        <span class="landing-log-dot" />
        <span class="truncate">{{ logs[active] }}</span>
      </div>
      <span class="landing-chip"><UIcon name="i-lucide-calendar-clock" class="size-3.5" /> 09:00</span>
      <span class="landing-chip"><UIcon name="i-lucide-coins" class="size-3.5" /> 2 cr</span>
    </div>
  </div>
</template>
