<script setup lang="ts">
const route = useRoute()
const auth = useAuth()
const items = [
  { label: 'Обзор', icon: 'i-lucide-layout-dashboard', to: '/dashboard' },
  { label: 'Цепочки', icon: 'i-lucide-workflow', to: '/workflows' },
  { label: 'Запуски', icon: 'i-lucide-activity', to: '/runs' },
  { label: 'Биллинг', icon: 'i-lucide-wallet', to: '/billing' },
  { label: 'Профиль', icon: 'i-lucide-user', to: '/profile' }
]
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <NuxtLink to="/dashboard" class="brand app-logo">Yakun</NuxtLink>
      <nav class="app-nav">
        <UButton
          v-for="item in items"
          :key="item.to"
          v-bind="item"
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
