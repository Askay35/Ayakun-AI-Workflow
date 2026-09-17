<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

const { t } = useI18n()
useSeoMeta({
  title: () => t('legal.deliveryTitle'),
  description: () => t('legal.deliveryDesc')
})
</script>

<template>
  <main class="shell legal-page">
    <div class="legal-card reveal">
      <p class="eyebrow">{{ t('legal.deliveryEyebrow') }}</p>
      <h1 class="page-title">{{ t('legal.deliveryHeading') }}</h1>
      <p class="legal-meta muted">{{ t('legal.deliveryLead') }}</p>

      <div class="legal-body">
        <h2>{{ t('legal.buyTitle') }}</h2>
        <p>{{ t('legal.buyText', { brand: LEGAL.brand }) }}</p>

        <h2>{{ t('legal.afterTitle') }}</h2>
        <ol>
          <li>{{ t('legal.after1') }}</li>
          <li>{{ t('legal.after2') }}</li>
          <li>{{ t('legal.after3') }}</li>
          <li>{{ t('legal.after4') }}</li>
        </ol>

        <h2>{{ t('legal.termTitle') }}</h2>
        <p>{{ t('legal.termText') }}</p>

        <h2>{{ t('legal.missingTitle') }}</h2>
        <p>
          {{ t('legal.missingText', { email: LEGAL.email }) }}
        </p>
      </div>

      <div class="legal-actions">
        <NuxtLink to="/terms" class="site-button">{{ t('nav.terms') }}</NuxtLink>
        <NuxtLink to="/contacts" class="site-button secondary">{{ t('nav.contacts') }}</NuxtLink>
      </div>
    </div>
  </main>
</template>
