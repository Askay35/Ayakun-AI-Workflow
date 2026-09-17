<script setup lang="ts">
const { embedded = false } = defineProps<{ embedded?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
useAppTitle(computed(() => t('titles.editor')))
</script>

<template>
  <div class="editor-mobile-gate" :class="{ embedded }" @click.self="embedded && emit('close')">
    <div class="editor-mobile-card reveal">
      <div class="editor-mobile-glow" aria-hidden="true" />
      <span class="editor-mobile-icon">
        <UIcon name="i-lucide-monitor-smartphone" class="size-7" />
      </span>
      <p class="eyebrow">{{ t('mobileEditor.eyebrow') }}</p>
      <h1 class="editor-mobile-title">{{ t('mobileEditor.title') }}</h1>
      <p class="editor-mobile-copy">{{ t('mobileEditor.copy') }}</p>
      <div class="editor-mobile-actions">
        <UButton
          v-if="embedded"
          class="w-full sm:w-auto"
          :label="t('mobileEditor.ok')"
          icon="i-lucide-check"
          size="lg"
          @click="emit('close')"
        />
        <UButton
          v-else
          class="w-full sm:w-auto"
          to="/workflows"
          :label="t('mobileEditor.toList')"
          icon="i-lucide-arrow-left"
          size="lg"
        />
        <UButton class="w-full sm:w-auto" to="/dashboard" :label="t('mobileEditor.home')" color="neutral" variant="ghost" size="lg" />
      </div>
    </div>
  </div>
</template>
