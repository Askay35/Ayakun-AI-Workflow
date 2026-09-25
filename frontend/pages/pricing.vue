<script setup lang="ts">
import type { Plan } from '~/types/api'
import { sortCreditPacks } from '~/utils/credits'

const { t, tm } = useI18n()
useSeoMeta({
  title: () => t('pricing.title'),
  description: () => t('pricing.description')
})

const api = useApi()
const auth = useAuth()
const fallback: Plan[] = [
  { id: 1, code: 'free', name: 'Пробный', price: 0, currency: 'RUB', limits: { included_credits: 100, max_files: 20, max_storage_mb: 100 } },
  { id: 2, code: 'starter', name: 'Старт', price: 390, currency: 'RUB', limits: { included_credits: 2000, max_files: 50, max_storage_mb: 500 } },
  { id: 3, code: 'pro', name: 'Про', price: 990, currency: 'RUB', limits: { included_credits: 6500, max_files: 100, max_storage_mb: 1024 } },
  { id: 4, code: 'max', name: 'Супер', price: 1990, currency: 'RUB', limits: { included_credits: 15000, max_files: 500, max_storage_mb: 5120 } }
]
const { data: plans } = await useAsyncData('public-plans', () => api.billing.plans().catch(() => fallback))
const ordered = computed(() => sortCreditPacks(plans.value || fallback))
const featuredCode = 'pro'
const ctaTarget = computed(() => (auth.user.value ? '/billing' : '/login'))
const factIcons = ['i-lucide-calendar-clock', 'i-lucide-gauge', 'i-lucide-hard-drive', 'i-lucide-trending-up']
const facts = computed(() => tm<Array<{ title: string; text: string }>>('pricing.facts').map((item, index) => ({
  ...item,
  icon: factIcons[index]
})))
</script>

<template>
  <main>
    <section class="section page-hero">
      <div class="shell">
        <div class="mx-auto mb-14 max-w-3xl text-center reveal">
          <p class="eyebrow">{{ t('pricing.eyebrow') }}</p>
          <h1 class="page-title !text-[clamp(38px,5.5vw,64px)] !tracking-[-0.04em]">{{ t('pricing.heading') }}</h1>
          <p class="mx-auto mt-5 max-w-2xl text-lg leading-8 muted">
            {{ t('pricing.lead') }}
          </p>
  
        </div>
        <div class="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <PlanCard
            v-for="(plan, index) in ordered"
            :key="plan.id"
            :plan="plan"
            :featured="plan.code === featuredCode"
            :top="index === ordered.length - 1"
            class="reveal"
            :style="{ animationDelay: `${index * 90}ms` }"
          >
            <UButton
              :to="ctaTarget"
              :label="Number(plan.price) ? t('pricing.buy') : t('nav.startFree')"
              block
              size="lg"
              class="credit-pack-cta"
              :color="plan.code === featuredCode || !Number(plan.price) ? 'neutral' : 'primary'"
              :variant="Number(plan.price) ? 'solid' : 'outline'"
            />
          </PlanCard>
        </div>
      </div>
    </section>

    <section class="section alt">
      <div class="shell grid items-center gap-10 md:grid-cols-2">
        <div class="section-heading mb-0!">
          <p class="eyebrow">{{ t('pricing.howEyebrow') }}</p>
          <h2>{{ t('pricing.howTitle') }}</h2>
          <p>{{ t('pricing.howLead') }}</p>
        </div>
        <div class="grid gap-3">
          <div v-for="item in facts" :key="item.title" class="flex items-start gap-4 rounded-2xl border border-[var(--line)] bg-white p-5 shadow-[var(--shadow-sm)]">
            <span class="tile shrink-0"><UIcon :name="item.icon" class="size-5" /></span>
            <div>
              <strong class="block text-[16px]">{{ item.title }}</strong>
              <p class="mb-0 mt-1 text-sm leading-6 muted">{{ item.text }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
