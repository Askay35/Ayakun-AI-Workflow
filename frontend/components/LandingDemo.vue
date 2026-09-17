<script setup lang="ts">
const video = ref<HTMLVideoElement>()
const paused = ref(false)
const reduceMotion = ref(false)
let observer: IntersectionObserver | undefined

onMounted(() => {
  reduceMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const el = video.value
  if (!el || reduceMotion.value) return
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && !paused.value) void el.play()
    else el.pause()
  }, { threshold: 0.28 })
  observer.observe(el)
})
onBeforeUnmount(() => observer?.disconnect())

const toggle = () => {
  const el = video.value
  if (!el || reduceMotion.value) return
  if (el.paused) {
    paused.value = false
    void el.play()
    return
  }
  paused.value = true
  el.pause()
}
</script>

<template>
  <figure class="demo-stage">
    <div class="demo-window">
      <div class="demo-chrome">
        <span class="demo-dots" aria-hidden="true"><i /><i /><i /></span>
        <p class="demo-chrome-title">Редактор цепочки</p>
        <span class="landing-run-pill" :class="{ 'is-live': !paused && !reduceMotion }">
          <i />
          {{ reduceMotion ? 'Пример' : paused ? 'Пауза' : 'Сборка' }}
        </span>
      </div>
      <button class="demo-screen" type="button" :aria-label="paused ? 'Смотреть запись' : 'Поставить на паузу'" @click="toggle">
        <video
          ref="video"
          class="demo-video"
          poster="/videos/demo-poster.jpg"
          preload="metadata"
          muted
          loop
          playsinline
          disablepictureinpicture
        >
          <source src="/videos/2.mp4" type="video/mp4" />
        </video>
        <span v-if="paused || reduceMotion" class="demo-play">
          <UIcon name="i-lucide-play" class="size-5" />
        </span>
      </button>
    </div>
    <figcaption class="demo-caption">Перетащите узлы, соедините стрелками и запустите — без кода.</figcaption>
  </figure>
</template>
