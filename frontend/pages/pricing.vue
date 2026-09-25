<script setup lang="ts">
import type { Plan } from '~/types/api'
import { bestValuePackCode, formatCredits, packCredits, sortCreditPacks } from '~/utils/credits'

const { t, tm, formatMoney } = useI18n()
useSeoMeta({
  title: () => t('pricing.title'),
  description: () => t('pricing.description')
})

const api = useApi()
const fallback: Plan[] = [
  { id: 1, code: 'free', name: 'Старт', price: 0, currency: 'RUB', limits: { included_credits: 1000 } },
  { id: 2, code: 'starter', name: 'Запас', price: 390, currency: 'RUB', limits: { included_credits: 2000 } },
  { id: 3, code: 'pro', name: 'Запас', price: 990, currency: 'RUB', limits: { included_credits: 6500 } },
  { id: 4, code: 'max', name: 'Запас', price: 1990, currency: 'RUB', limits: { included_credits: 15000 } }
]
const { data: plans } = await useAsyncData('public-plans', () => api.billing.plans().catch(() => fallback))
const ordered = computed(() => sortCreditPacks(plans.value || fallback))
const featuredCode = computed(() => bestValuePackCode(ordered.value))
const factIcons = ['i-lucide-wallet', 'i-lucide-gauge', 'i-lucide-eye', 'i-lucide-infinity']
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
          <article
            v-for="(plan, index) in ordered"
            :key="plan.id"
            class="panel credit-pack reveal"
            :class="{
              'is-gift': !Number(plan.price),
              'is-featured': plan.code === featuredCode
            }"
            :style="{ animationDelay: `${index * 90}ms` }"
          >
            <span v-if="plan.code === featuredCode" class="credit-pack-badge">{{ t('pricing.better') }}</span>
            <span class="credit-pack-icon">
              <UIcon :name="Number(plan.price) ? 'i-lucide-coins' : 'i-lucide-gift'" class="size-5" />
            </span>
            <p class="credit-pack-credits">{{ formatCredits(packCredits(plan)) }}</p>
            <p class="credit-pack-unit">{{ t('common.tokens') }}</p>
            <span class="credit-pack-rule" aria-hidden="true" />
            <p class="credit-pack-price">
              <template v-if="Number(plan.price)">
                <strong>{{ formatMoney(Number(plan.price)) }}</strong>
                <span>₽</span>
              </template>
              <template v-else>
                <strong>{{ t('pricing.free') }}</strong>
              </template>
            </p>
            <UButton
              to="/login"
              :label="Number(plan.price) ? t('pricing.buy') : t('nav.startFree')"
              block
              size="lg"
              class="credit-pack-cta mt-auto"
              :color="plan.code === featuredCode ? 'neutral' : Number(plan.price) ? 'primary' : 'neutral'"
              :variant="Number(plan.price) ? 'solid' : 'outline'"
            />
          </article>
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
