<script setup lang="ts">
const { embedded = false } = defineProps<{ embedded?: boolean }>()
const emit = defineEmits<{ close: [] }>()
useAppTitle('Редактор')
</script>

<template>
  <div class="editor-mobile-gate" :class="{ embedded }">
    <div class="editor-mobile-card reveal">
      <div class="editor-mobile-glow" aria-hidden="true" />
      <span class="editor-mobile-icon">
        <UIcon name="i-lucide-monitor-smartphone" class="size-7" />
      </span>
      <p class="eyebrow">Только на компьютере</p>
      <h1 class="editor-mobile-title">
        Визуальный редактор<br>недоступен на телефоне
      </h1>
      <p class="editor-mobile-copy">
        Сборка цепочек рассчитана на большой экран: холст, связи узлов и боковые панели.
        Откройте Ayakun с ноутбука или компьютера — черновики сохранятся.
      </p>
      <div class="editor-mobile-actions">
        <UButton
          v-if="embedded"
          label="Понятно"
          icon="i-lucide-check"
          size="lg"
          @click="emit('close')"
        />
        <UButton
          v-else
          to="/workflows"
          label="К списку цепочек"
          icon="i-lucide-arrow-left"
          size="lg"
        />
        <UButton to="/dashboard" label="На главную" color="neutral" variant="ghost" size="lg" />
      </div>
    </div>
  </div>
</template>
