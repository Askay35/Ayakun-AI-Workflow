<script setup lang="ts">
import type { Plan } from '~/types/api'
import { formatCredits, formatStorage, packCredits, planStorageBytes } from '~/utils/credits'

const props = defineProps<{
  plan: Plan
  featured?: boolean
  current?: boolean
  /** Самый дорогой тариф: переходить дальше некуда. */
  top?: boolean
}>()

const { t, locale, formatMoney } = useI18n()
const paid = computed(() => Number(props.plan.price) > 0)
const features = computed(() => {
  const files = Number(props.plan.limits?.max_files || 0)
  const bytes = planStorageBytes(props.plan)
  const items = [
    paid.value
      ? t('pricing.tokensMonth', { n: formatCredits(packCredits(props.plan)) })
      : t('pricing.tokensOnce', { n: formatCredits(packCredits(props.plan)) })
  ]
  if (files && bytes) items.push(t('pricing.storage', { files, size: formatStorage(bytes, locale.value) }))
  items.push(paid.value ? t('pricing.featureMedia') : t('pricing.featureNoMedia'))
  items.push(paid.value ? t('pricing.featureBlocks') : t('pricing.featureTemplates'))
  if (paid.value && !props.top) items.push(t('pricing.featureUpgrade'))
  return items
})
</script>

<template>
  <article
    class="panel credit-pack plan-card"
    :class="{ 'is-gift': !paid, 'is-featured': featured, 'is-current': current }"
  >
    <span v-if="current" class="credit-pack-badge">{{ t('billing.current') }}</span>
    <span v-else-if="featured" class="credit-pack-badge">{{ t('pricing.better') }}</span>
    <span class="credit-pack-icon">
      <UIcon :name="paid ? 'i-lucide-rocket' : 'i-lucide-gift'" class="size-5" />
    </span>
    <p class="plan-card-name">{{ plan.name }}</p>
    <p class="credit-pack-price">
      <template v-if="paid">
        <strong>{{ formatMoney(Number(plan.price)) }} ₽</strong>
        <span>{{ t('pricing.perMonth') }}</span>
      </template>
      <strong v-else>{{ t('pricing.free') }}</strong>
    </p>
    <span class="credit-pack-rule" aria-hidden="true" />
    <ul class="plan-card-features">
      <li v-for="item in features" :key="item">
        <UIcon name="i-lucide-check" class="size-4 shrink-0" />
        <span>{{ item }}</span>
      </li>
    </ul>
    <div class="mt-auto">
      <slot />
    </div>
  </article>
</template>
