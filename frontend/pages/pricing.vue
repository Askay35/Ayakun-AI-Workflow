<script setup lang="ts">
import type { Plan } from '~/types/api'

const api = useApi()
const fallback: Plan[] = [
  { id: 1, code: 'free', name: 'Free', price: 0, currency: 'RUB', limits: { included_credits: 500 } },
  { id: 2, code: 'starter', name: 'Starter', price: 990, currency: 'RUB', limits: { included_credits: 5000 } },
  { id: 3, code: 'pro', name: 'Pro', price: 1990, currency: 'RUB', limits: { included_credits: 15000 } },
  { id: 4, code: 'max', name: 'Max', price: 3990, currency: 'RUB', limits: { included_credits: 50000 } }
]
const { data: plans } = await useAsyncData('public-plans', () => api.billing.plans().catch(() => fallback))
const ordered = computed(() => {
  const list = plans.value || fallback
  const rank = { free: 0, starter: 1, pro: 2, max: 3 } as Record<string, number>
  return [...list].sort((a, b) => (rank[a.code] ?? 9) - (rank[b.code] ?? 9))
})
const planMeta: Record<string, { title: string; pitch: string; action: string }> = {
  free: { title: 'Free', pitch: 'Чтобы собрать первые цепочки и проверить идею.', action: 'Попробовать бесплатно' },
  starter: { title: 'Starter', pitch: 'Для регулярных личных и рабочих задач.', action: 'Выбрать Starter' },
  pro: { title: 'Pro', pitch: 'Для большого числа ежедневных запусков.', action: 'Выбрать Pro' },
  max: { title: 'Max', pitch: 'Для интенсивных автоматизаций.', action: 'Выбрать Max' }
}
const meta = (plan: Plan) => planMeta[plan.code] || { title: plan.name, pitch: 'Гибкий тариф для ваших задач.', action: 'Выбрать' }
const featuresFor = (plan: Plan) => {
  const balance = Number(plan.limits.included_credits || 0)
  return [
    `${balance.toLocaleString('ru')} credits на балансе`,
    'любое число цепочек',
    'запуск вручную и по расписанию',
    'цена каждого запуска видна заранее'
  ]
}
</script>

<template>
  <main>
    <section class="section">
      <div class="shell">
        <div class="mx-auto mb-14 max-w-3xl text-center reveal">
          <p class="eyebrow">Простая экономика</p>
          <h1 class="page-title !text-[clamp(42px,6vw,76px)]">Платите за результат,<br>а не за ограничения</h1>
          <p class="mx-auto mt-5 max-w-2xl text-lg leading-8 muted">
            На каждом тарифе доступны все действия, расписания и любое число цепочек.
            Отличается только запас credits и внутренний лимит одного запуска.
          </p>
        </div>
        <div class="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <article
            v-for="(plan, index) in ordered"
            :key="plan.id"
            class="panel relative flex flex-col p-7 reveal"
            :class="plan.code === 'starter' ? 'border-violet-500 shadow-[0_24px_60px_rgba(103,88,238,.16)]' : ''"
            :style="{ animationDelay: `${index * 90}ms` }"
          >
            <span v-if="plan.code === 'starter'" class="absolute -top-3 right-6 rounded-full bg-[#6758ee] px-3 py-1 text-xs font-extrabold text-white">Выбирают чаще</span>
            <p class="eyebrow">{{ plan.code === 'free' ? 'Для знакомства' : plan.code === 'starter' ? 'Для регулярной работы' : 'Больше запусков' }}</p>
            <h2 class="mb-2 text-3xl font-extrabold">{{ meta(plan).title }}</h2>
            <p class="min-h-12 text-sm leading-6 muted">{{ meta(plan).pitch }}</p>
            <div class="my-7 flex items-end gap-2">
              <strong class="text-5xl font-extrabold">{{ Number(plan.price) ? Number(plan.price).toLocaleString('ru') : '0' }}</strong>
              <span class="mb-1 muted">{{ Number(plan.price) ? '₽ / месяц' : '₽' }}</span>
            </div>
            <ul class="mb-8 space-y-3">
              <li v-for="feature in featuresFor(plan)" :key="feature" class="flex gap-3 text-sm">
                <span class="grid size-5 shrink-0 place-items-center rounded-full bg-[#eeecff] text-[#6758ee]"><UIcon name="i-lucide-check" class="size-3.5" /></span>
                {{ feature }}
              </li>
            </ul>
            <UButton
              to="/login"
              :label="meta(plan).action"
              block
              size="lg"
              class="mt-auto"
              :color="plan.code === 'starter' ? 'primary' : 'neutral'"
              :variant="plan.code === 'starter' ? 'solid' : 'outline'"
            />
          </article>
        </div>
        <p class="mx-auto mt-8 max-w-2xl text-center text-sm leading-6 muted">
          Оценка запуска приблизительная. Списываются только фактически использованные credits после ответа провайдера.
        </p>
      </div>
    </section>

    <section class="section alt">
      <div class="shell grid items-center gap-10 md:grid-cols-2">
        <div class="section-heading !mb-0">
          <p class="eyebrow">Без искусственных рамок</p>
          <h2>Создавайте столько, сколько нужно</h2>
          <p>Не нужно выбирать тариф из-за одной дополнительной цепочки. Пока на балансе есть credits — все ваши автоматизации работают.</p>
        </div>
        <div class="grid gap-3">
          <div v-for="item in ['Без лимита цепочек', 'Расписание доступно сразу', 'Все режимы обработки', 'История запусков и результатов']" :key="item" class="flex items-center gap-3 rounded-2xl bg-white/5 p-4">
            <span class="grid size-9 place-items-center rounded-xl bg-[#c9f169] text-[#1b2408]"><UIcon name="i-lucide-check" /></span>
            <strong>{{ item }}</strong>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
