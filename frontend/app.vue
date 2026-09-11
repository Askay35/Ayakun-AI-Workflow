<script setup lang="ts">
useHead({
  titleTemplate: (title?: string) => (!title || title === 'Ayakun' ? 'Ayakun' : `${title} · Ayakun`)
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
