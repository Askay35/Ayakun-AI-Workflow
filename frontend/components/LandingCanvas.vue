<script setup lang="ts">
const { t, tm } = useI18n()

const chain = computed(() => [
  { id: 'search', label: t('landing.canvas.searchLabel'), caption: t('landing.canvas.searchCaption'), icon: 'i-lucide-search', accent: '#2bbf8e' },
  { id: 'prompt', label: t('landing.canvas.promptLabel'), caption: t('landing.canvas.promptCaption'), icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  { id: 'telegram', label: t('landing.canvas.telegramLabel'), caption: t('landing.canvas.telegramCaption'), icon: 'i-lucide-send', accent: '#2aa8e0' }
])

const ghosts = [
  { id: 'http', label: 'HTTP', icon: 'i-lucide-globe', accent: '#f59e0b' },
  { id: 'branch', label: 'IF / ELSE', icon: 'i-lucide-git-branch', accent: '#e8b84a' }
] as const

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
    <div class="landing-canvas-glow" />
    <div class="landing-canvas-grid" />

    <div class="landing-canvas-toolbar">
      <div class="min-w-0">
        <p class="m-0 text-[13px] font-extrabold tracking-tight text-white">{{ t('landing.canvas.name') }}</p>
        <p class="m-0 mt-1 text-[11px] text-white/40">{{ t('landing.canvas.schedule') }}</p>
      </div>
      <span class="landing-run-pill" :class="{ 'is-live': running }">
        <i />
        {{ running ? t('landing.canvas.running') : t('landing.canvas.done') }}
      </span>
    </div>

    <div class="landing-stage">
      <div class="landing-side">
        <article
          v-for="ghost in ghosts"
          :key="ghost.id"
          class="landing-ghost"
          :style="{ '--node-accent': ghost.accent }"
        >
          <span class="landing-node-icon">
            <UIcon :name="ghost.icon" class="size-3.5" />
          </span>
          {{ ghost.label }}
        </article>
      </div>

      <div class="landing-chain">
        <template v-for="(node, index) in chain" :key="node.id">
          <div v-if="index > 0" class="landing-link" />
          <article
            class="landing-node"
            :class="{ 'is-active': active === index, 'is-done': active > index }"
            :style="{ '--node-accent': node.accent }"
          >
            <span class="landing-handle in" />
            <span class="landing-node-icon">
              <UIcon :name="node.icon" class="size-4" />
            </span>
            <div class="min-w-0">
              <p class="mb-0 text-[10px] font-extrabold uppercase tracking-[0.14em] text-white/35">{{ node.label }}</p>
              <p class="mb-0 truncate text-[13px] font-extrabold text-white">{{ node.caption }}</p>
            </div>
            <span class="landing-handle out" />
          </article>
        </template>
      </div>
    </div>

    <div class="landing-foot">
      <div class="landing-log">
        <span class="landing-log-dot" />
        <span class="truncate">{{ logs[active] }}</span>
      </div>
      <div class="landing-float landing-float-cron">
        <UIcon name="i-lucide-calendar-clock" class="size-3.5" />
        09:00
      </div>
      <div class="landing-float landing-float-cost">
        <UIcon name="i-lucide-coins" class="size-3.5" />
        2 cr
      </div>
    </div>
  </div>
</template>
