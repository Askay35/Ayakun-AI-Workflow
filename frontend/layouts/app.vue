<script setup lang="ts">
import { APP_NAV_ITEMS } from '~/utils/app-nav'

const route = useRoute()
const auth = useAuth()
const { t } = useI18n()
useAppTitle()
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <NuxtLink to="/dashboard" class="brand app-logo mb-7 mx-2.5">
        Ayakun
      </NuxtLink>
      <nav class="app-nav">
        <UButton
          v-for="item in APP_NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          :icon="item.icon"
          :label="t(`nav.${item.key}`)"
          block
          class="justify-start text-white"
          :variant="item.to === '/docs' ? (route.path === '/docs' ? 'soft' : 'ghost') : (route.path.startsWith(item.to) ? 'soft' : 'ghost')"
          color="neutral"
        />
      </nav>
      <div class="app-user">
        <LanguageSwitcher tone="dark" class="mb-3" />
        <div class="mb-2 flex items-center gap-2">
          <span class="status-dot online" />
          <p class="m-0 truncate text-sm font-semibold">{{ auth.user.value?.name || auth.user.value?.email || t('common.account') }}</p>
        </div>
        <UButton :label="t('common.logout')" icon="i-lucide-log-out" color="neutral" variant="ghost" size="sm" class="px-0 text-white/60" @click="auth.logout" />
      </div>
    </aside>
    <main class="app-main"><slot /></main>
  </div>
</template>
