<script setup lang="ts">
const chain = [
  { id: 'search', label: 'Поиск в сети', caption: 'Новости рынка', icon: 'i-lucide-search', accent: '#2bbf8e' },
  { id: 'prompt', label: 'Обработка', caption: 'Выделить главное', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  { id: 'telegram', label: 'Telegram', caption: 'Утренний обзор', icon: 'i-lucide-send', accent: '#2aa8e0' }
] as const

const ghosts = [
  { id: 'http', label: 'HTTP', icon: 'i-lucide-globe', accent: '#f59e0b' },
  { id: 'branch', label: 'IF / ELSE', icon: 'i-lucide-git-branch', accent: '#e8b84a' }
] as const

const logs = [
  'Ищу свежие материалы…',
  'Сжимаю 12 источников в вывод',
  'Отправляю в Telegram'
]

const active = ref(0)
const running = ref(true)
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    active.value = chain.length - 1
    running.value = false
    return
  }
  timer = setInterval(() => {
    active.value = (active.value + 1) % chain.length
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
        <p class="m-0 text-[13px] font-extrabold tracking-tight text-white">Утренний обзор рынка</p>
        <p class="m-0 mt-1 text-[11px] text-white/40">Будни · 09:00 · ≈ 2 credits</p>
      </div>
      <span class="landing-run-pill" :class="{ 'is-live': running }">
        <i />
        {{ running ? 'Выполняется' : 'Готово' }}
      </span>
    </div>

    <article
      v-for="ghost in ghosts"
      :key="ghost.id"
      class="landing-ghost"
      :class="`is-${ghost.id}`"
      :style="{ '--node-accent': ghost.accent }"
    >
      <span class="landing-node-icon">
        <UIcon :name="ghost.icon" class="size-3.5" />
      </span>
      {{ ghost.label }}
    </article>

    <svg class="landing-wires" viewBox="0 0 100 100" preserveAspectRatio="none">
      <path class="landing-wire" d="M28 38 C 40 38, 44 28, 54 28" />
      <path class="landing-wire" d="M72 32 C 82 36, 78 58, 70 64" />
    </svg>
    <span class="landing-packet is-a" />
    <span class="landing-packet is-b" />

    <article
      v-for="(node, index) in chain"
      :key="node.id"
      class="landing-node"
      :class="[`is-${node.id}`, { 'is-active': active === index, 'is-done': active > index }]"
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

    <div class="landing-float landing-float-cron">
      <UIcon name="i-lucide-calendar-clock" class="size-3.5" />
      09:00
    </div>
    <div class="landing-float landing-float-cost">
      <UIcon name="i-lucide-coins" class="size-3.5" />
      2 cr
    </div>
    <div class="landing-log">
      <span class="landing-log-dot" />
      {{ logs[active] }}
    </div>
  </div>
</template>
