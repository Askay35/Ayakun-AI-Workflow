<script setup lang="ts">
import { APP_NAV_ITEMS, activeNavPath } from '~/utils/app-nav'
import { formatCredits } from '~/utils/credits'

const route = useRoute()
const auth = useAuth()
const api = useApi()
const { t } = useI18n()
useAppTitle()

const { data: wallet } = await useAuthAsyncData(
  'app-wallet',
  () => api.billing.wallet().catch(() => null)
)

const isActive = (to: string) => activeNavPath(route.path) === to
const userName = computed(() => auth.user.value?.name || auth.user.value?.email || t('common.account'))
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <NuxtLink to="/dashboard" class="brand app-logo app-sidebar-logo">
        <img src="~/assets/images/logo.png" alt="" class="app-logo-mark" width="32" height="32" />
        Ayakun
      </NuxtLink>
      <nav class="app-nav">
        <NuxtLink
          v-for="item in APP_NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          class="app-nav-item"
          :class="{ 'is-active': isActive(item.to) }"
        >
          <UIcon :name="item.icon" class="size-[18px]" />
          {{ t(`nav.${item.key}`) }}
        </NuxtLink>
      </nav>
      <NuxtLink v-if="wallet" to="/billing" class="app-balance">
        <span class="app-balance-label"><UIcon name="i-lucide-coins" class="size-4" /> {{ t('app.balance') }}</span>
        <span class="app-balance-value">{{ formatCredits(wallet.balance) }} <small>{{ t('common.tokens') }}</small></span>
        <span class="app-balance-cta">{{ t('app.topUp') }} <UIcon name="i-lucide-arrow-right" class="size-3.5" /></span>
      </NuxtLink>
      <div class="app-user">
        <div class="app-user-row">
          <span class="app-avatar">{{ userName.slice(0, 1).toUpperCase() }}</span>
          <p class="app-user-name">{{ userName }}</p>
          <button type="button" class="app-icon-button" :aria-label="t('common.logout')" :title="t('common.logout')" @click="auth.logout">
            <UIcon name="i-lucide-log-out" class="size-4" />
          </button>
        </div>
        <LanguageSwitcher />
      </div>
    </aside>
    <main class="app-main"><slot /></main>
  </div>
</template>
