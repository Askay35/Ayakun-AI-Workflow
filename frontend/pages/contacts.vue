<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

const { t } = useI18n()
useSeoMeta({
  title: () => t('legal.contactsTitle'),
  description: () => t('legal.contactsDesc')
})
</script>

<template>
  <main class="shell legal-page">
    <div class="legal-card reveal">
      <span class="legal-icon"><UIcon name="i-lucide-contact-round" class="size-6" /></span>
      <p class="eyebrow">{{ t('legal.contactsEyebrow') }}</p>
      <h1 class="page-title">{{ t('legal.contactsHeading') }}</h1>
      <p class="legal-meta muted">{{ t('legal.contactsLead') }}</p>

      <div class="legal-body">
        <div class="requisites">
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">{{ t('legal.contractor') }}</p>
            <p class="mb-0 font-extrabold">{{ LEGAL.entity }}</p>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">{{ t('legal.phone') }}</p>
            <a :href="`tel:${LEGAL.phone}`" class="legal-link">{{ LEGAL.phoneDisplay }}</a>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">{{ t('legal.email') }}</p>
            <a :href="`mailto:${LEGAL.email}`" class="legal-link">{{ LEGAL.email }}</a>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">{{ t('legal.address') }}</p>
            <p class="mb-0">{{ LEGAL.address }}</p>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">{{ t('common.inn') }}</p>
            <p class="mb-0">{{ LEGAL.inn }}</p>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">{{ t('common.ogrnip') }}</p>
            <p class="mb-0">{{ LEGAL.ogrnip }}</p>
          </div>
        </div>

        <h2>{{ t('legal.contactsTopics') }}</h2>
        <p>{{ t('legal.contactsTopicsText') }}</p>
      </div>

      <div class="legal-actions">
        <NuxtLink to="/terms" class="site-button secondary">{{ t('nav.terms') }}</NuxtLink>
        <NuxtLink to="/privacy" class="site-button secondary">{{ t('nav.privacy') }}</NuxtLink>
        <NuxtLink to="/delivery" class="site-button secondary">{{ t('nav.delivery') }}</NuxtLink>
      </div>
    </div>
  </main>
</template>
