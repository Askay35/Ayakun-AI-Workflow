<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

const auth = useAuth()
useAppTitle()
</script>

<template>
  <div class="public-wrap">
    <header class="public-header">
      <div class="shell public-header-inner">
        <NuxtLink to="/" class="brand public-logo">
          <span class="logo-mark">Y</span>
          Ayakun
        </NuxtLink>
        <nav class="public-nav">
          <NuxtLink to="/#features" class="nav-link nav-hide">Возможности</NuxtLink>
          <NuxtLink to="/#how" class="nav-link nav-hide">Как работает</NuxtLink>
          <NuxtLink to="/pricing" class="nav-link nav-hide">Тарифы</NuxtLink>
          <NuxtLink
            :to="auth.user.value ? '/dashboard' : '/login'"
            class="site-button secondary login-link"
          >
            {{ auth.user.value ? 'Кабинет' : 'Войти' }}
          </NuxtLink>
          <NuxtLink :to="auth.user.value ? '/workflows' : '/login'" class="site-button">
            {{ auth.user.value ? 'Мои цепочки' : 'Начать бесплатно' }}
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
          <p class="mb-0 mt-2 text-sm muted">ИНН {{ LEGAL.inn }} · ОГРНИП {{ LEGAL.ogrnip }}</p>
        </div>
        <nav class="public-footer-links">
          <NuxtLink to="/delivery">Как получить услугу</NuxtLink>
          <NuxtLink to="/terms">Публичная оферта</NuxtLink>
          <NuxtLink to="/contacts">Контакты и реквизиты</NuxtLink>
          <a :href="`mailto:${LEGAL.email}`">{{ LEGAL.email }}</a>
          <a :href="`tel:${LEGAL.phone}`">{{ LEGAL.phoneDisplay }}</a>
        </nav>
      </div>
    </footer>
  </div>
</template>
