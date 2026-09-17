<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

const auth = useAuth()
const { t } = useI18n()
useAppTitle()
</script>

<template>
  <div class="public-wrap">
    <header class="public-header">
      <div class="shell public-header-inner">
        <NuxtLink to="/" class="brand app-logo">
          <img src="~/assets/images/logo.png" alt="" class="app-logo-mark" width="32" height="32" />
          Ayakun
        </NuxtLink>
        <nav class="public-nav">
          <NuxtLink to="/#features" class="nav-link nav-hide">{{ t('nav.features') }}</NuxtLink>
          <NuxtLink to="/#examples" class="nav-link nav-hide">{{ t('nav.examples') }}</NuxtLink>
          <NuxtLink to="/#how" class="nav-link nav-hide">{{ t('nav.how') }}</NuxtLink>
          <NuxtLink to="/pricing" class="nav-link nav-hide">{{ t('nav.pricing') }}</NuxtLink>
          <NuxtLink to="/docs" class="nav-link nav-hide">{{ t('nav.docs') }}</NuxtLink>
          <LanguageSwitcher />
          <a
            :href="LEGAL.telegramChannel"
            class="social-icon-link"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="t('nav.telegramChannelAria')"
            :title="t('nav.telegramChannel')"
          >
            <UIcon name="i-simple-icons-telegram" class="size-5" />
          </a>
          <NuxtLink
            :to="auth.user.value ? '/dashboard' : '/login'"
            class="site-button secondary login-link"
          >
            {{ auth.user.value ? t('nav.cabinet') : t('nav.login') }}
          </NuxtLink>
          <NuxtLink :to="auth.user.value ? '/workflows' : '/login'" class="site-button">
            {{ auth.user.value ? t('nav.myWorkflows') : t('nav.startFree') }}
            <UIcon name="i-lucide-arrow-up-right" />
          </NuxtLink>
        </nav>
      </div>
    </header>
    <slot />
    <footer class="public-footer">
      <div class="shell public-footer-inner">
        <div>
          <p class="brand public-footer-logo">Ayakun</p>
          <p class="mb-0 text-sm leading-6 muted">{{ LEGAL.entity }}</p>
          <p class="mb-0 mt-2 text-sm muted">{{ t('common.inn') }} {{ LEGAL.inn }} · {{ t('common.ogrnip') }} {{ LEGAL.ogrnip }}</p>
          <a
            :href="LEGAL.telegramChannel"
            class="social-icon-link footer-social"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="t('nav.telegramChannelAria')"
            :title="t('nav.telegramChannel')"
          >
            <UIcon name="i-simple-icons-telegram" class="size-5" />
          </a>
        </div>
        <nav class="public-footer-links">
          <NuxtLink to="/delivery">{{ t('nav.delivery') }}</NuxtLink>
          <NuxtLink to="/docs">{{ t('nav.docs') }}</NuxtLink>
          <NuxtLink to="/terms">{{ t('nav.terms') }}</NuxtLink>
          <NuxtLink to="/privacy">{{ t('nav.privacy') }}</NuxtLink>
          <NuxtLink to="/contacts">{{ t('nav.contacts') }}</NuxtLink>
          <a :href="`mailto:${LEGAL.email}`">{{ LEGAL.email }}</a>
          <a :href="`tel:${LEGAL.phone}`">{{ LEGAL.phoneDisplay }}</a>
        </nav>
      </div>
    </footer>
  </div>
</template>
