<script setup lang="ts">
const auth = useAuth()
</script>

<template>
  <div class="public-wrap">
    <header class="public-header">
      <div class="shell public-header-inner">
        <NuxtLink to="/" class="brand public-logo">
          <span class="logo-mark">Y</span>
          Yakun
        </NuxtLink>
        <nav class="public-nav">
          <NuxtLink to="/#how" class="nav-link nav-hide">Как работает</NuxtLink>
          <NuxtLink to="/pricing" class="nav-link nav-hide">Тарифы</NuxtLink>
          <NuxtLink
            :to="auth.user.value ? '/dashboard' : '/auth'"
            class="site-button secondary login-link"
          >
            {{ auth.user.value ? 'Кабинет' : 'Войти' }}
          </NuxtLink>
          <NuxtLink :to="auth.user.value ? '/workflows' : '/auth'" class="site-button">
            {{ auth.user.value ? 'Мои цепочки' : 'Начать бесплатно' }}
            <UIcon name="i-lucide-arrow-up-right" />
          </NuxtLink>
        </nav>
      </div>
    </header>
    <slot />
  </div>
</template>
