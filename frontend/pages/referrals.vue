<script setup lang="ts">
import { formatCredits } from '~/utils/credits'

definePageMeta({ layout: 'app', middleware: 'auth' })
const api = useApi()
const toast = useToast()
const { t, formatDate, formatDateOnly } = useI18n()
const { data: summary } = await useAuthAsyncData('referrals', () => api.referrals.summary())

const link = computed(() => {
  if (!summary.value?.code || !import.meta.client) return ''
  return `${location.origin}/?ref=${summary.value.code}`
})
const copy = async () => {
  if (!link.value) return
  await navigator.clipboard.writeText(link.value)
  toast.add({ title: t('referrals.copied'), color: 'success' })
}
const stepIcons = ['i-lucide-link', 'i-lucide-user-plus', 'i-lucide-gift']
const steps = computed(() => [1, 2, 3].map((n, index) => ({
  icon: stepIcons[index],
  title: t(`referrals.step${n}Title`),
  text: t(`referrals.step${n}Text`, { bonus: formatCredits(summary.value?.bonus ?? 200) })
})))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">{{ t('referrals.eyebrow') }}</p>
        <h1 class="page-title">{{ t('referrals.title') }}</h1>
        <p class="muted">{{ t('referrals.lead', { bonus: formatCredits(summary?.bonus ?? 200) }) }}</p>
      </div>
    </div>

    <section class="panel referral-hero">
      <div class="min-w-0">
        <p class="mb-1 text-sm font-bold muted">{{ t('referrals.linkTitle') }}</p>
        <div class="referral-link">
          <UIcon name="i-lucide-link" class="size-4 shrink-0 text-[#6d4aff]" />
          <span class="truncate">{{ link || '…' }}</span>
        </div>
        <p class="mb-0 mt-2 text-xs muted">{{ t('referrals.codeLabel') }} <strong class="text-[var(--ink)]">{{ summary?.code }}</strong></p>
      </div>
      <UButton :label="t('referrals.copy')" icon="i-lucide-copy" size="lg" :disabled="!link" @click="copy" />
    </section>

    <div class="grid-cards mt-4">
      <div class="panel metric-card" style="--card-accent:#6d4aff">
        <span class="metric-icon"><UIcon name="i-lucide-users" class="size-6" /></span>
        <div>
          <p class="mb-0 text-sm font-semibold muted">{{ t('referrals.invited') }}</p>
          <p class="metric-value">{{ summary?.invited ?? 0 }}</p>
          <p class="mb-0 mt-1 text-xs muted">{{ t('referrals.paying', { n: summary?.paying ?? 0 }) }}</p>
        </div>
      </div>
      <div class="panel metric-card" style="--card-accent:#12a67a">
        <span class="metric-icon"><UIcon name="i-lucide-coins" class="size-6" /></span>
        <div>
          <p class="mb-0 text-sm font-semibold muted">{{ t('referrals.earned') }}</p>
          <p class="metric-value">{{ formatCredits(summary?.earned) }}</p>
          <p class="mb-0 mt-1 text-xs muted">{{ t('common.tokens') }}</p>
        </div>
      </div>
    </div>

    <div class="mt-8 grid gap-4 md:grid-cols-3">
      <article v-for="(step, index) in steps" :key="step.title" class="panel p-5">
        <span class="tile mb-3"><UIcon :name="step.icon" class="size-5" /></span>
        <p class="mb-1 text-xs font-extrabold uppercase tracking-[0.12em] text-[#6d4aff]">{{ t('referrals.stepN', { n: index + 1 }) }}</p>
        <h3 class="mb-1 text-base font-extrabold">{{ step.title }}</h3>
        <p class="mb-0 text-sm leading-6 muted">{{ step.text }}</p>
      </article>
    </div>

    <div class="mt-8 grid gap-4 lg:grid-cols-2">
      <div class="panel p-6">
        <h2 class="mb-1 text-xl font-extrabold tracking-tight">{{ t('referrals.listTitle') }}</h2>
        <p class="mb-4 text-sm muted">{{ t('referrals.listLead') }}</p>
        <div v-if="summary?.referrals?.length" class="row-list">
          <div v-for="(item, index) in summary.referrals" :key="`${item.name}-${index}`" class="flex items-center justify-between gap-4 py-3">
            <div class="flex min-w-0 items-center gap-3">
              <span class="app-avatar">{{ item.name.slice(0, 1).toUpperCase() }}</span>
              <div class="min-w-0">
                <p class="mb-0 truncate font-semibold">{{ item.name }}</p>
                <p class="mb-0 text-xs muted">{{ t('referrals.joined', { date: formatDateOnly(item.joined_at) }) }}</p>
              </div>
            </div>
            <div class="shrink-0 text-right">
              <p class="mb-0 text-sm font-bold" :class="item.earned > 0 ? 'text-[#15803d]' : 'muted'">
                {{ item.earned > 0 ? `+${formatCredits(item.earned)}` : t('referrals.noPurchases') }}
              </p>
              <p v-if="item.purchases" class="mb-0 text-xs muted">{{ t('referrals.purchases', { n: item.purchases }) }}</p>
            </div>
          </div>
        </div>
        <p v-else class="mb-0 text-sm muted">{{ t('referrals.listEmpty') }}</p>
      </div>
      <div class="panel p-6">
        <h2 class="mb-1 text-xl font-extrabold tracking-tight">{{ t('referrals.rewardsTitle') }}</h2>
        <p class="mb-4 text-sm muted">{{ t('referrals.rewardsLead') }}</p>
        <div v-if="summary?.rewards?.length" class="row-list">
          <div v-for="(reward, index) in summary.rewards" :key="index" class="flex justify-between gap-4 py-3">
            <div class="min-w-0">
              <p class="mb-0 font-medium">
                {{ reward.role === 'referee'
                  ? t('referrals.rewardReferee')
                  : t('referrals.rewardReferrer', { name: reward.referee_name || '—', plan: reward.plan_name || '' }) }}
              </p>
              <p class="mb-0 mt-1 text-xs muted">{{ formatDate(reward.created_at) }}</p>
            </div>
            <strong class="shrink-0 text-[#15803d]">+{{ formatCredits(reward.amount) }}</strong>
          </div>
        </div>
        <p v-else class="mb-0 text-sm muted">{{ t('referrals.rewardsEmpty') }}</p>
      </div>
    </div>
  </div>
</template>
