<script setup lang="ts">
definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const { t } = useI18n()
const { data: templates } = await useAuthAsyncData('app-templates', () => api.templates.list())
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">{{ t('templates.eyebrow') }}</p>
        <h1 class="page-title">{{ t('templates.appTitle') }}</h1>
        <p class="muted">{{ t('templates.appLead') }}</p>
      </div>
    </div>
    <TemplatesGallery :templates="templates || []" filters />
  </div>
</template>
