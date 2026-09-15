<script setup lang="ts">
const SITE_TITLE = 'Ayakun — визуальная автоматизация с ИИ без кода'

useHead({
  titleTemplate: (title?: string) => (
    !title || title === 'Ayakun' || title === SITE_TITLE
      ? SITE_TITLE
      : `${title} · Ayakun`
  )
})
</script>

<template>
  <UApp>
    <NuxtLoadingIndicator color="#14b8a6" />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
