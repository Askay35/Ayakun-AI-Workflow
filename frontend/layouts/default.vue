<script setup lang="ts">
const auth = useAuth()
const links = [
  { label: 'Возможности', to: '/#features' },
  { label: 'Тарифы', to: '/pricing' }
]
</script>

<template>
  <div>
    <header class="border-b border-default bg-white/90 backdrop-blur">
      <div class="page !py-3 flex items-center justify-between">
        <NuxtLink to="/" class="text-xl font-bold text-primary">Yakun</NuxtLink>
        <nav class="flex items-center gap-2">
          <UButton v-for="link in links" :key="link.to" v-bind="link" color="neutral" variant="ghost" />
          <UButton :to="auth.user.value ? '/dashboard' : '/auth'">
            {{ auth.user.value ? 'К проектам' : 'Войти' }}
          </UButton>
        </nav>
      </div>
    </header>
    <slot />
  </div>
</template>
