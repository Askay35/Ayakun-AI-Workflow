<script setup lang="ts">
const api = useApi()
const { t } = useI18n()
useSeoMeta({
  title: () => t('templates.title'),
  description: () => t('templates.description')
})
const { data: templates } = await useAsyncData('public-templates', () => api.templates.list().catch(() => []))
</script>

<template>
  <main>
    <section class="section page-hero">
      <div class="shell">
        <div class="mx-auto mb-12 max-w-3xl text-center reveal">
          <p class="eyebrow">{{ t('templates.eyebrow') }}</p>
          <h1 class="page-title !text-[clamp(36px,5vw,58px)] !tracking-[-0.04em]">{{ t('templates.heading') }}</h1>
          <p class="mx-auto mt-5 max-w-2xl text-lg leading-8 muted">{{ t('templates.lead', { n: templates?.length || 30 }) }}</p>
        </div>
        <TemplatesGallery :templates="templates || []" filters />
      </div>
    </section>
  </main>
</template>
