<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

const auth = useAuth()
const route = useRoute()
const { t } = useI18n()
useAppTitle()

const menuOpen = ref(false)

const closeMenu = () => {
  menuOpen.value = false
}

watch(() => route.fullPath, closeMenu)

watch(menuOpen, (open) => {
  if (!import.meta.client) return
  document.body.style.overflow = open ? 'hidden' : ''
})

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') closeMenu()
}

const onResize = () => {
  if (window.matchMedia('(min-width: 981px)').matches) closeMenu()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  if (import.meta.client) document.body.style.overflow = ''
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div class="public-wrap">
    <header class="public-header">
      <div v-if="menuOpen" class="public-menu-backdrop" @click="closeMenu" />
      <div class="shell public-header-inner">
        <NuxtLink to="/" class="brand app-logo" @click="closeMenu">
          <img src="~/assets/images/logo.png" alt="Ayakun" class="app-logo-mark" width="32" height="32" />
          Ayakun
        </NuxtLink>
        <button
          type="button"
          class="public-menu-toggle"
          :aria-expanded="menuOpen"
          aria-controls="public-menu"
          :aria-label="menuOpen ? t('nav.menuClose') : t('nav.menuOpen')"
          @click="menuOpen = !menuOpen"
        >
          <UIcon :name="menuOpen ? 'i-lucide-x' : 'i-lucide-menu'" class="size-5" />
        </button>
        <nav id="public-menu" class="public-nav" :class="{ 'is-open': menuOpen }">
          <NuxtLink to="/#features" class="nav-link" @click="closeMenu">{{ t('nav.features') }}</NuxtLink>
          <NuxtLink to="/templates" class="nav-link" @click="closeMenu">{{ t('nav.templates') }}</NuxtLink>
          <NuxtLink to="/#how" class="nav-link" @click="closeMenu">{{ t('nav.how') }}</NuxtLink>
          <NuxtLink to="/pricing" class="nav-link" @click="closeMenu">{{ t('nav.pricing') }}</NuxtLink>
          <NuxtLink to="/docs" class="nav-link" @click="closeMenu">{{ t('nav.docs') }}</NuxtLink>
          <div class="public-nav-meta">
            <LanguageSwitcher />
            <a
              :href="LEGAL.telegramChannel"
              class="social-icon-link"
              target="_blank"
              rel="noopener noreferrer"
              :aria-label="t('nav.telegramChannelAria')"
              :title="t('nav.telegramChannel')"
            >
              <UIcon name="i-simple-icons-telegram" class="size-5" />
            </a>
          </div>
          <div class="public-nav-actions">
            <NuxtLink
              :to="auth.user.value ? '/dashboard' : '/login'"
              class="site-button secondary login-link"
              @click="closeMenu"
            >
              {{ auth.user.value ? t('nav.cabinet') : t('nav.login') }}
            </NuxtLink>
            <NuxtLink :to="auth.user.value ? '/workflows' : '/login'" class="site-button" @click="closeMenu">
              {{ auth.user.value ? t('nav.myWorkflows') : t('nav.startFree') }}
              <UIcon name="i-lucide-arrow-up-right" />
            </NuxtLink>
          </div>
        </nav>
      </div>
    </header>
    <slot />
    <footer class="public-footer">
      <div class="shell">
        <div class="public-footer-inner">
          <div>
            <NuxtLink to="/" class="brand app-logo public-footer-logo">
              <img src="~/assets/images/logo.png" alt="" class="app-logo-mark" width="32" height="32" />
              Ayakun
            </NuxtLink>
            <p class="mb-0 max-w-64 text-sm leading-6 muted">{{ t('footer.tagline') }}</p>
            <a
              :href="LEGAL.telegramChannel"
              class="social-icon-link footer-social"
              target="_blank"
              rel="noopener noreferrer"
              :aria-label="t('nav.telegramChannelAria')"
              :title="t('nav.telegramChannel')"
            >
              <UIcon name="i-simple-icons-telegram" class="size-5" />
            </a>
          </div>
          <nav class="public-footer-col">
            <h4>{{ t('footer.product') }}</h4>
            <NuxtLink to="/#features">{{ t('nav.features') }}</NuxtLink>
            <NuxtLink to="/templates">{{ t('nav.templates') }}</NuxtLink>
            <NuxtLink to="/pricing">{{ t('nav.pricing') }}</NuxtLink>
            <NuxtLink to="/docs">{{ t('nav.docs') }}</NuxtLink>
          </nav>
          <nav class="public-footer-col">
            <h4>{{ t('footer.legal') }}</h4>
            <NuxtLink to="/delivery">{{ t('nav.delivery') }}</NuxtLink>
            <NuxtLink to="/terms">{{ t('nav.terms') }}</NuxtLink>
            <NuxtLink to="/privacy">{{ t('nav.privacy') }}</NuxtLink>
            <NuxtLink to="/contacts">{{ t('nav.contacts') }}</NuxtLink>
          </nav>
          <div class="public-footer-col">
            <h4>{{ t('footer.contact') }}</h4>
            <a :href="`mailto:${LEGAL.email}`">{{ LEGAL.email }}</a>
            <a :href="`tel:${LEGAL.phone}`">{{ LEGAL.phoneDisplay }}</a>
          </div>
        </div>
        <div class="public-footer-bottom">
          <span>{{ LEGAL.entity }}</span>
          <span>{{ t('common.inn') }} {{ LEGAL.inn }} · {{ t('common.ogrnip') }} {{ LEGAL.ogrnip }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>
