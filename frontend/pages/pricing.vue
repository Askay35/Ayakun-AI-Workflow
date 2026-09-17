<script setup lang="ts">
import type { Plan } from '~/types/api'
import { bestValuePackCode, formatCredits, packCredits, sortCreditPacks } from '~/utils/credits'

useSeoMeta({
  title: 'Цены',
  description: 'Покупаете credits — списывается только фактический расход запуска. Без подписки и срока действия.'
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
const facts = [
  { icon: 'i-lucide-wallet', title: 'Пакет = credits', text: 'Платите один раз — на баланс сразу приходит указанный запас.' },
  { icon: 'i-lucide-gauge', title: 'Списание по факту', text: 'Уходит только стоимость запуска, а не весь пакет сразу.' },
  { icon: 'i-lucide-eye', title: 'Цена до старта', text: 'В редакторе виден максимум запуска, до того как цепочка пойдёт.' },
  { icon: 'i-lucide-infinity', title: 'Не сгорают', text: 'Остаток лежит на балансе, пока вы его не потратите.' }
]
</script>

<template>
  <main>
    <section class="section">
      <div class="shell">
        <div class="mx-auto mb-14 max-w-3xl text-center reveal">
          <p class="eyebrow">Credits</p>
          <h1 class="page-title !text-[clamp(42px,6vw,76px)]">Платите только за нужный объём</h1>
          <p class="mx-auto mt-5 max-w-2xl text-lg leading-8 muted">
            Никаких подписок или скрытых ступеней — вы приобретаете пакет credits и тратите их по мере использования.
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
            <span v-if="plan.code === featuredCode" class="credit-pack-badge">Выгоднее</span>
            <span class="credit-pack-icon">
              <UIcon :name="Number(plan.price) ? 'i-lucide-coins' : 'i-lucide-gift'" class="size-5" />
            </span>
            <p class="credit-pack-credits">{{ formatCredits(packCredits(plan)) }}</p>
            <p class="credit-pack-unit">credits</p>
            <span class="credit-pack-rule" aria-hidden="true" />
            <p class="credit-pack-price">
              <template v-if="Number(plan.price)">
                <strong>{{ Number(plan.price).toLocaleString('ru-RU') }}</strong>
                <span>₽</span>
              </template>
              <template v-else>
                <strong>Бесплатно</strong>
              </template>
            </p>
            <UButton
              to="/login"
              :label="Number(plan.price) ? 'Купить' : 'Начать бесплатно'"
              block
              size="lg"
              class="credit-pack-cta mt-auto"
              :class="{ 'text-white!': plan.code === 'free' }"
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
          <p class="eyebrow">Как это работает</p>
          <h2>Один баланс на все цепочки</h2>
          <p>Не нужно сравнивать функции пакетов. Отличается только число credits, которое вы кладёте на счёт.</p>
        </div>
        <div class="grid gap-3">
          <div v-for="item in facts" :key="item.title" class="flex items-start gap-3 rounded-2xl bg-white/5 p-4">
            <span class="grid size-9 shrink-0 place-items-center rounded-xl bg-[#c9f169] text-[#1b2408]"><UIcon :name="item.icon" /></span>
            <div>
              <strong class="block">{{ item.title }}</strong>
              <p class="mb-0 mt-1 text-sm leading-5 text-white/55">{{ item.text }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
