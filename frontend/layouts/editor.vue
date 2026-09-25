<script setup lang="ts">
import { APP_NAV_ITEMS, activeNavPath } from '~/utils/app-nav'
import { formatCredits } from '~/utils/credits'

const route = useRoute()
const auth = useAuth()
const api = useApi()
const { t } = useI18n()
useAppTitle()

const { data: wallet } = await useAuthAsyncData(
  'editor-wallet',
  () => api.billing.wallet().catch(() => null)
)
</script>

<template>
  <div class="editor-shell">
    <header class="app-header">
      <NuxtLink to="/dashboard" class="brand app-header-logo">
        <img src="~/assets/images/logo.png" alt="" class="app-logo-mark" width="28" height="28" />
        Ayakun
      </NuxtLink>
      <nav class="app-header-nav">
        <NuxtLink
          v-for="item in APP_NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          class="app-header-link"
          :class="{ 'is-active': activeNavPath(route.path) === item.to }"
          :title="t(`nav.${item.key}`)"
        >
          <UIcon :name="item.icon" class="size-4" />
          <span class="app-header-link-label">{{ t(`nav.${item.key}`) }}</span>
        </NuxtLink>
      </nav>
      <div class="app-header-user">
        <LanguageSwitcher />
        <NuxtLink
          v-if="wallet"
          to="/billing"
          class="app-header-balance"
          :title="`${formatCredits(wallet.balance)} ${t('common.tokens')}`"
        >
          <UIcon name="i-lucide-coins" class="size-3.5" />
          {{ formatCredits(wallet.balance) }}
          <span class="app-header-balance-unit">{{ t('common.tokens') }}</span>
        </NuxtLink>
        <span class="app-header-name">{{ auth.user.value?.name || auth.user.value?.email || t('common.account') }}</span>
        <button type="button" class="app-icon-button" :aria-label="t('common.logout')" :title="t('common.logout')" @click="auth.logout">
          <UIcon name="i-lucide-log-out" class="size-4" />
        </button>
      </div>
    </header>
    <main class="editor-shell-main">
      <slot />
    </main>
  </div>
</template>
