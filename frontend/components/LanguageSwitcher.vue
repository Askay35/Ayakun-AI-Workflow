<script setup lang="ts">
const { locale, setLocale, t } = useI18n()

const props = withDefaults(defineProps<{ tone?: 'light' | 'dark' }>(), { tone: 'light' })
</script>

<template>
  <div class="lang-switch" :class="`is-${props.tone}`" role="group" :aria-label="t('lang.switch')">
    <button
      type="button"
      :class="{ active: locale === 'ru' }"
      :aria-pressed="locale === 'ru'"
      :title="t('lang.ru')"
      @click="setLocale('ru')"
    >
      RU
    </button>
    <button
      type="button"
      :class="{ active: locale === 'en' }"
      :aria-pressed="locale === 'en'"
      :title="t('lang.en')"
      @click="setLocale('en')"
    >
      EN
    </button>
  </div>
</template>
