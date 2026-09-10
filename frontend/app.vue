<script setup lang="ts">
useHead({
  titleTemplate: (title?: string) => (!title || title === 'Yakun' ? 'Yakun' : `${title} · Yakun`)
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
