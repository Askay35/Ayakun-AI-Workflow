<script setup lang="ts">
import { APP_NAV_ITEMS } from '~/utils/app-nav'

const route = useRoute()
const auth = useAuth()
useAppTitle()
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <NuxtLink to="/dashboard" class="brand app-logo">Yakun</NuxtLink>
      <nav class="app-nav">
        <UButton
          v-for="item in APP_NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          :icon="item.icon"
          :label="item.label"
          block
          class="justify-start text-white"
          :variant="route.path.startsWith(item.to) ? 'soft' : 'ghost'"
          color="neutral"
        />
      </nav>
      <div class="app-user">
        <div class="mb-2 flex items-center gap-2">
          <span class="status-dot online" />
          <p class="m-0 truncate text-sm font-semibold">{{ auth.user.value?.name || auth.user.value?.email || 'Аккаунт' }}</p>
        </div>
        <UButton label="Выйти" icon="i-lucide-log-out" color="neutral" variant="ghost" size="sm" class="px-0 text-white/60" @click="auth.logout" />
      </div>
    </aside>
    <main class="app-main"><slot /></main>
  </div>
</template>
