<script setup lang="ts">
import { APP_NAV_ITEMS } from '~/utils/app-nav'
import { formatCredits } from '~/utils/credits'

const route = useRoute()
const auth = useAuth()
const api = useApi()
useAppTitle()

const { data: wallet } = await useAuthAsyncData(
  'editor-wallet',
  () => api.billing.wallet().catch(() => null)
)
</script>

<template>
  <div class="editor-shell">
    <header class="app-header">
      <NuxtLink to="/dashboard" class="brand app-header-logo">Ayakun</NuxtLink>
      <nav class="app-header-nav">
        <UButton
          v-for="item in APP_NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          :icon="item.icon"
          :label="item.label"
          size="sm"
          class="text-white/80"
          :variant="route.path.startsWith(item.to) ? 'soft' : 'ghost'"
          color="neutral"
        />
      </nav>
      <div class="app-header-user">
        <NuxtLink
          v-if="wallet"
          to="/billing"
          class="app-header-balance"
          :title="`${formatCredits(wallet.balance)} credits`"
        >
          <UIcon name="i-lucide-coins" class="size-3.5" />
          {{ formatCredits(wallet.balance) }}
          <span class="app-header-balance-unit">credits</span>
        </NuxtLink>
        <span class="status-dot online" />
        <span class="max-w-40 truncate text-sm font-semibold text-white/80">{{ auth.user.value?.name || auth.user.value?.email || 'Аккаунт' }}</span>
        <UButton icon="i-lucide-log-out" color="neutral" variant="ghost" size="sm" class="text-white/50" @click="auth.logout" />
      </div>
    </header>
    <main class="editor-shell-main">
      <slot />
    </main>
  </div>
</template>
