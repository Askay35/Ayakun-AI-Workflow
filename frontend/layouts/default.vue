<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

const auth = useAuth()
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
          <NuxtLink to="/#features" class="nav-link nav-hide">Возможности</NuxtLink>
          <NuxtLink to="/#examples" class="nav-link nav-hide">Примеры</NuxtLink>
          <NuxtLink to="/#how" class="nav-link nav-hide">Как работает</NuxtLink>
          <NuxtLink to="/pricing" class="nav-link nav-hide">Цены</NuxtLink>
          <NuxtLink to="/docs" class="nav-link nav-hide">Документация</NuxtLink>
          <a
            :href="LEGAL.telegramChannel"
            class="social-icon-link"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Telegram-канал Ayakun"
            title="Telegram-канал"
          >
            <UIcon name="i-simple-icons-telegram" class="size-5" />
          </a>
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
          <a
            :href="LEGAL.telegramChannel"
            class="social-icon-link footer-social"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Telegram-канал Ayakun"
            title="Telegram-канал"
          >
            <UIcon name="i-simple-icons-telegram" class="size-5" />
          </a>
        </div>
        <nav class="public-footer-links">
          <NuxtLink to="/delivery">Как получить услугу</NuxtLink>
          <NuxtLink to="/docs">Документация</NuxtLink>
          <NuxtLink to="/terms">Публичная оферта</NuxtLink>
          <NuxtLink to="/privacy">Политика конфиденциальности</NuxtLink>
          <NuxtLink to="/contacts">Контакты и реквизиты</NuxtLink>
          <a :href="`mailto:${LEGAL.email}`">{{ LEGAL.email }}</a>
          <a :href="`tel:${LEGAL.phone}`">{{ LEGAL.phoneDisplay }}</a>
        </nav>
      </div>
    </footer>
  </div>
</template>
