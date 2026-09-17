<script setup lang="ts">
const { locale, t } = useI18n()

useHead({
  htmlAttrs: { lang: locale },
  titleTemplate: (title?: string) => {
    const site = t('meta.siteTitle')
    return !title || title === 'Ayakun' || title === site ? site : `${title} · Ayakun`
  },
  meta: [
    { name: 'description', content: () => t('meta.siteDescription') },
    { property: 'og:title', content: () => t('meta.siteTitle') },
    { property: 'og:description', content: () => t('meta.siteDescription') }
  ]
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
