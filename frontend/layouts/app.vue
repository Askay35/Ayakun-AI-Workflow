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
  <div class="min-h-screen md:grid md:grid-cols-[230px_1fr]">
    <aside class="border-r border-default bg-white p-4">
      <NuxtLink to="/dashboard" class="mb-7 block text-2xl font-bold text-primary">Yakun</NuxtLink>
      <nav class="space-y-1">
        <UButton
          v-for="item in items"
          :key="item.to"
          v-bind="item"
          block
          class="justify-start"
          :variant="route.path.startsWith(item.to) ? 'soft' : 'ghost'"
          color="neutral"
        />
      </nav>
      <div class="mt-8 border-t border-default pt-4">
        <p class="truncate text-sm font-medium">{{ auth.user.value?.name || auth.user.value?.email || 'Аккаунт' }}</p>
        <UButton label="Выйти" color="neutral" variant="link" class="px-0" @click="auth.logout" />
      </div>
    </aside>
    <main class="min-w-0"><slot /></main>
  </div>
</template>
