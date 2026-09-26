<script setup lang="ts">
import { APP_NAV_ITEMS, activeNavPath } from '~/utils/app-nav'
import { formatCredits } from '~/utils/credits'

const route = useRoute()
const auth = useAuth()
const api = useApi()
const { t } = useI18n()
useAppTitle()

const menuOpen = ref(false)
watch(() => route.path, () => { menuOpen.value = false })

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
        <LanguageSwitcher class="app-header-desktop" />
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
        <span class="app-header-name app-header-desktop">{{ auth.user.value?.name || auth.user.value?.email || t('common.account') }}</span>
        <button type="button" class="app-icon-button app-header-desktop" :aria-label="t('common.logout')" :title="t('common.logout')" @click="auth.logout">
          <UIcon name="i-lucide-log-out" class="size-4" />
        </button>
        <button
          type="button"
          class="app-icon-button app-header-burger"
          :aria-expanded="menuOpen"
          :aria-label="menuOpen ? t('nav.menuClose') : t('nav.menuOpen')"
          @click="menuOpen = !menuOpen"
        >
          <UIcon :name="menuOpen ? 'i-lucide-x' : 'i-lucide-menu'" class="size-5" />
        </button>
      </div>
    </header>
    <template v-if="menuOpen">
      <div class="app-menu-backdrop" @click="menuOpen = false" />
      <nav class="app-menu" :aria-label="t('nav.menuOpen')">
        <NuxtLink
          v-for="item in APP_NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          class="app-menu-link"
          :class="{ 'is-active': activeNavPath(route.path) === item.to }"
        >
          <UIcon :name="item.icon" class="size-[18px]" />
          {{ t(`nav.${item.key}`) }}
        </NuxtLink>
        <div class="app-menu-foot">
          <span class="app-menu-name">{{ auth.user.value?.name || auth.user.value?.email || t('common.account') }}</span>
          <LanguageSwitcher />
        </div>
        <button type="button" class="app-menu-link is-logout" @click="auth.logout">
          <UIcon name="i-lucide-log-out" class="size-[18px]" />
          {{ t('common.logout') }}
        </button>
      </nav>
    </template>
    <main class="editor-shell-main">
      <slot />
    </main>
  </div>
</template>
