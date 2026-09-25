<script setup lang="ts">
import type { AdminStats, AdminStatsGranularity, AdminStatsMetric } from '~/types/api'
import type { AdminChartSeries } from '~/components/AdminChart.vue'
import { apiErrorMessage } from '~/composables/useApi'
import { formatCredits } from '~/utils/credits'
import { statusLabel } from '~/utils/run-status'

const props = defineProps<{ credentials: string }>()
const emit = defineEmits<{ 'open-user': [id: number] }>()

const RANGES: Array<{ value: string; label: string; granularity: AdminStatsGranularity; points: number }> = [
  { value: '7d', label: '7 дней', granularity: 'day', points: 7 },
  { value: '30d', label: '30 дней', granularity: 'day', points: 30 },
  { value: '13w', label: '13 недель', granularity: 'week', points: 13 },
  { value: '12m', label: '12 месяцев', granularity: 'month', points: 12 },
  { value: '24m', label: '24 месяца', granularity: 'month', points: 24 }
]
const PREVIOUS_LABEL: Record<AdminStatsGranularity, string> = {
  day: 'к прошлому дню',
  week: 'к прошлой неделе',
  month: 'к прошлому месяцу'
}
const COLORS = ['#6d4aff', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
const REFERRAL_COLOR = '#1baf7a'
const PROVIDER_LABELS: Record<string, string> = { email: 'Email', google: 'Google', telegram: 'Telegram' }

const api = useApi()
const toast = useToast()
const { t } = useI18n()
const range = ref('30d')
const stats = ref<AdminStats>()
const loading = ref(false)
const selected = computed(() => RANGES.find(item => item.value === range.value) || RANGES[1]!)

const load = async () => {
  loading.value = true
  try {
    stats.value = await api.admin.stats(props.credentials, {
      granularity: selected.value.granularity,
      points: selected.value.points,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow'
    })
  } catch (error) {
    toast.add({ title: 'Не удалось загрузить статистику', description: apiErrorMessage(error), color: 'error' })
  } finally {
    loading.value = false
  }
}
watch(range, load)
onMounted(load)

const money = (value: number) => `${Math.round(value).toLocaleString('ru-RU')} ₽`
const count = (value: number) => Math.round(value).toLocaleString('ru-RU')
const signed = (value: number, format: (value: number) => string) =>
  `${value > 0 ? '+' : value < 0 ? '−' : ''}${format(Math.abs(value))}`
const percent = (value: number | null) => value == null ? null : `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toLocaleString('ru-RU')}%`

const parseDay = (value: string) => {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year!, month! - 1, day!)
}
const shortLabel = (value: string) => {
  const date = parseDay(value)
  if (stats.value?.granularity === 'month') {
    return date.toLocaleDateString('ru', { month: 'short', year: '2-digit' }).replace(' г.', '')
  }
  return date.toLocaleDateString('ru', { day: 'numeric', month: 'short' }).replace('.', '')
}
const longLabel = (value: string) => {
  const date = parseDay(value)
  if (stats.value?.granularity === 'month') {
    const text = date.toLocaleDateString('ru', { month: 'long', year: 'numeric' }).replace(' г.', '')
    return text.charAt(0).toUpperCase() + text.slice(1)
  }
  const text = date.toLocaleDateString('ru', { day: 'numeric', month: 'long', year: 'numeric' }).replace(' г.', '')
  return stats.value?.granularity === 'week' ? `Неделя с ${text}` : text
}

const series = computed(() => stats.value?.series || [])
const labels = computed(() => series.value.map(point => shortLabel(point.start)))
const titles = computed(() => series.value.map(point => longLabel(point.start)))

const kpis = computed(() => {
  const data = stats.value
  if (!data) return []
  const tile = (label: string, icon: string, accent: string, metric: AdminStatsMetric, format: (v: number) => string, hint?: string) => ({
    label, icon, accent, hint, value: format(metric.value),
    delta: metric.delta, deltaText: signed(metric.delta, format), pct: percent(metric.delta_pct)
  })
  return [
    tile('Регистрации', 'i-lucide-user-plus', '#6d4aff', data.registrations, count),
    tile('Доход', 'i-lucide-banknote', '#12a67a', data.revenue, money),
    tile('Платящие пользователи', 'i-lucide-badge-russian-ruble', '#e58a0b', data.paying_users, count),
    tile('Средний чек', 'i-lucide-receipt', '#3b82f6', data.avg_check, money),
    tile('По рефералам', 'i-lucide-gift', '#1baf7a', data.referral_registrations, count),
    tile('Активные пользователи', 'i-lucide-activity', '#e87ba4', data.active_users, count, 'Запускали цепочки'),
    tile('Запуски', 'i-lucide-play', '#eb6834', data.runs, count)
  ]
})

const registrationSeries = computed<AdminChartSeries[]>(() => [
  { key: 'organic', label: 'Сами', color: COLORS[0]!, values: series.value.map(p => p.registrations - p.referral_registrations) },
  { key: 'referral', label: 'По рефералам', color: REFERRAL_COLOR, values: series.value.map(p => p.referral_registrations) }
])
const registrationDetails = (index: number) => {
  const point = series.value[index]
  if (!point) return []
  const pct = percent(point.registrations_delta_pct)
  return [`Прирост ${PREVIOUS_LABEL[stats.value!.granularity]}: ${signed(point.registrations_delta, count)}${pct ? ` (${pct})` : ''}`]
}
const usersSeries = computed<AdminChartSeries[]>(() => [
  { key: 'users', label: 'Пользователей', color: COLORS[0]!, values: series.value.map(p => p.users_total) }
])

const planColor = computed(() => Object.fromEntries(
  (stats.value?.plans || []).map((plan, index) => [plan.code, COLORS[index % COLORS.length]!])
))
const revenueSeries = computed<AdminChartSeries[]>(() => (stats.value?.plans || []).map(plan => ({
  key: plan.code,
  label: plan.name,
  color: planColor.value[plan.code]!,
  values: series.value.map(point => point.revenue_by_plan[plan.code] || 0)
})))
const revenueDetails = (index: number) => {
  const point = series.value[index]
  return point?.payments ? [`Оплат: ${point.payments}`] : []
}
const runsSeries = computed<AdminChartSeries[]>(() => [
  { key: 'ok', label: 'Без ошибок', color: COLORS[0]!, values: series.value.map(p => p.runs - p.failed_runs) },
  { key: 'failed', label: 'С ошибкой', color: COLORS[1]!, values: series.value.map(p => p.failed_runs) }
])
const runsDetails = (index: number) => {
  const point = series.value[index]
  return point?.credits_spent ? [`Списано: ${formatCredits(point.credits_spent)} токенов`] : []
}

const planRevenueTotal = computed(() => (stats.value?.plans || []).reduce((sum, plan) => sum + plan.revenue, 0))
const share = (value: number, total: number) => total ? Math.round(value / total * 100) : 0
const providerTotal = computed(() => (stats.value?.signup_providers || []).reduce((sum, item) => sum + item.count, 0))
const statusTotal = computed(() => (stats.value?.run_statuses || []).reduce((sum, item) => sum + item.count, 0))
const periodRows = computed(() => [...series.value].reverse())
</script>

<template>
  <div class="admin-dashboard">
    <div class="admin-filters">
      <div class="admin-segment" role="tablist">
        <button
          v-for="item in RANGES"
          :key="item.value"
          type="button"
          role="tab"
          :aria-selected="range === item.value"
          :class="{ 'is-active': range === item.value }"
          @click="range = item.value"
        >{{ item.label }}</button>
      </div>
      <p v-if="stats" class="admin-filters-note">
        Сравнение с предыдущим периодом такой же длины · {{ stats.timezone }}
      </p>
      <UButton icon="i-lucide-refresh-cw" color="neutral" variant="soft" :loading="loading" aria-label="Обновить" @click="load" />
    </div>

    <div v-if="!stats" class="admin-kpis">
      <USkeleton v-for="index in 8" :key="index" class="h-[128px] rounded-[20px]" />
    </div>

    <template v-else>
      <div class="admin-kpis" :class="{ 'is-loading': loading }">
        <article v-for="item in kpis" :key="item.label" class="panel admin-kpi" :style="{ '--card-accent': item.accent }">
          <div class="admin-kpi-head">
            <span class="admin-kpi-icon"><UIcon :name="item.icon" class="size-[18px]" /></span>
            <p>{{ item.label }}</p>
          </div>
          <p class="admin-kpi-value">{{ item.value }}</p>
          <p class="admin-kpi-delta">
            <span :class="item.delta > 0 ? 'is-up' : item.delta < 0 ? 'is-down' : 'is-flat'">
              <UIcon :name="item.delta > 0 ? 'i-lucide-trending-up' : item.delta < 0 ? 'i-lucide-trending-down' : 'i-lucide-minus'" class="size-3.5" />
              {{ item.deltaText }}<template v-if="item.pct"> · {{ item.pct }}</template>
            </span>
            <small>{{ item.hint || 'к прошлому периоду' }}</small>
          </p>
        </article>
        <article class="panel admin-kpi" style="--card-accent: #5535e6">
          <div class="admin-kpi-head">
            <span class="admin-kpi-icon"><UIcon name="i-lucide-percent" class="size-[18px]" /></span>
            <p>Конверсия в оплату</p>
          </div>
          <p class="admin-kpi-value">{{ stats.conversion_pct == null ? '—' : `${stats.conversion_pct.toLocaleString('ru-RU')}%` }}</p>
          <p class="admin-kpi-delta"><small>Новые пользователи периода, которые оплатили</small></p>
        </article>
      </div>

      <div class="admin-grid-2">
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Регистрации</h3>
              <p>Новые пользователи по периодам, из них по реферальным ссылкам</p>
            </div>
            <strong>{{ count(stats.registrations.value) }}</strong>
          </header>
          <AdminChart :labels="labels" :titles="titles" :series="registrationSeries" :format="count" :details="registrationDetails" />
        </section>
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Рост базы</h3>
              <p>Всего пользователей на конец периода</p>
            </div>
            <strong>{{ count(stats.totals.users) }}</strong>
          </header>
          <AdminChart type="line" :labels="labels" :titles="titles" :series="usersSeries" :format="count" />
        </section>
      </div>

      <div class="admin-grid-2">
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Доход</h3>
              <p>Успешные оплаты по тарифам, без выданных вручную</p>
            </div>
            <strong>{{ money(stats.revenue.value) }}</strong>
          </header>
          <AdminChart :labels="labels" :titles="titles" :series="revenueSeries" :format="money" :details="revenueDetails" />
        </section>
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Доход по тарифам</h3>
              <p>За период и за всё время</p>
            </div>
          </header>
          <div class="admin-table-wrap">
            <table class="admin-table admin-table-compact">
              <thead>
                <tr>
                  <th>Тариф</th>
                  <th class="text-right">За период</th>
                  <th class="text-right">Доля</th>
                  <th class="text-right">Всё время</th>
                  <th class="text-right">Подписки</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="plan in stats.plans" :key="plan.code">
                  <td>
                    <span class="admin-swatch" :style="{ background: planColor[plan.code] }" />
                    <span class="admin-primary">{{ plan.name }}</span>
                  </td>
                  <td class="text-right tabular-nums">
                    <p class="admin-primary">{{ money(plan.revenue) }}</p>
                    <p class="admin-meta">{{ plan.payments }} опл.</p>
                  </td>
                  <td class="text-right tabular-nums">{{ share(plan.revenue, planRevenueTotal) }}%</td>
                  <td class="text-right tabular-nums">
                    <p class="admin-primary">{{ money(plan.revenue_total) }}</p>
                    <p class="admin-meta">{{ plan.payments_total }} опл.</p>
                  </td>
                  <td class="text-right tabular-nums">{{ plan.active_subscriptions }}</td>
                </tr>
                <tr v-if="!stats.plans.length">
                  <td colspan="5" class="admin-empty">Оплат пока нет</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div class="admin-grid-2">
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Топ рефералов</h3>
              <p>Больше всего приглашённых за период, затем за всё время</p>
            </div>
          </header>
          <div class="admin-table-wrap">
            <table class="admin-table admin-table-compact">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Пригласил</th>
                  <th class="text-right">За период</th>
                  <th class="text-right">Всего</th>
                  <th class="text-right">Оплатили</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in stats.top_referrers" :key="item.user_id">
                  <td class="admin-rank">{{ index + 1 }}</td>
                  <td>
                    <button type="button" class="admin-link" @click="emit('open-user', item.user_id)">{{ item.name }}</button>
                    <p class="admin-meta">{{ item.email || `ID ${item.user_id}` }}</p>
                  </td>
                  <td class="text-right tabular-nums admin-primary">{{ item.referrals_period }}</td>
                  <td class="text-right tabular-nums">{{ item.referrals_total }}</td>
                  <td class="text-right tabular-nums">
                    <p class="admin-primary">{{ item.paid_referrals }}</p>
                    <p class="admin-meta">{{ money(item.revenue) }}</p>
                  </td>
                </tr>
                <tr v-if="!stats.top_referrers.length">
                  <td colspan="5" class="admin-empty">Регистраций по реферальным ссылкам пока нет</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Запуски цепочек</h3>
              <p>По периодам, с ошибкой и без</p>
            </div>
            <strong>{{ count(stats.runs.value) }}</strong>
          </header>
          <AdminChart :labels="labels" :titles="titles" :series="runsSeries" :format="count" :details="runsDetails" :height="200" />
        </section>
      </div>

      <div class="admin-grid-3">
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Способы входа</h3>
              <p>У новых пользователей периода</p>
            </div>
          </header>
          <div class="admin-meters">
            <div v-for="item in stats.signup_providers" :key="item.key" class="admin-meter">
              <p><span>{{ PROVIDER_LABELS[item.key] || item.key }}</span><strong>{{ item.count }} · {{ share(item.count, providerTotal) }}%</strong></p>
              <span class="admin-meter-track"><i :style="{ width: `${share(item.count, providerTotal)}%` }" /></span>
            </div>
            <p v-if="!stats.signup_providers.length" class="admin-empty-inline">Нет новых пользователей</p>
          </div>
        </section>
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>Статусы запусков</h3>
              <p>За период</p>
            </div>
          </header>
          <div class="admin-meters">
            <div v-for="item in stats.run_statuses" :key="item.key" class="admin-meter">
              <p><span>{{ statusLabel(item.key, t) }}</span><strong>{{ item.count }} · {{ share(item.count, statusTotal) }}%</strong></p>
              <span class="admin-meter-track"><i :style="{ width: `${share(item.count, statusTotal)}%` }" /></span>
            </div>
            <p v-if="!stats.run_statuses.length" class="admin-empty-inline">Запусков не было</p>
          </div>
        </section>
        <section class="panel admin-chart-card">
          <header>
            <div>
              <h3>За всё время</h3>
              <p>Состояние сервиса сейчас</p>
            </div>
          </header>
          <dl class="admin-facts">
            <div><dt>Пользователей</dt><dd>{{ count(stats.totals.users) }}</dd></div>
            <div><dt>Платящих</dt><dd>{{ count(stats.totals.paying_users) }}</dd></div>
            <div><dt>Доход</dt><dd>{{ money(stats.totals.revenue) }}</dd></div>
            <div><dt>Активных подписок</dt><dd>{{ count(stats.totals.active_subscriptions) }}</dd></div>
            <div><dt>Цепочек / опубликовано</dt><dd>{{ count(stats.totals.workflows) }} / {{ count(stats.totals.published_workflows) }}</dd></div>
            <div><dt>Запусков</dt><dd>{{ count(stats.totals.runs) }}</dd></div>
            <div><dt>Списано токенов за период</dt><dd>{{ formatCredits(stats.credits_spent) }}</dd></div>
            <div><dt>Себестоимость провайдеров</dt><dd>${{ stats.provider_cost_usd.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) }}</dd></div>
          </dl>
        </section>
      </div>

      <section class="panel admin-chart-card">
        <header>
          <div>
            <h3>По периодам</h3>
            <p>Регистрации, прирост к предыдущему периоду и доход</p>
          </div>
        </header>
        <div class="admin-table-wrap admin-periods">
          <table class="admin-table admin-table-compact">
            <thead>
              <tr>
                <th>Период</th>
                <th class="text-right">Регистрации</th>
                <th class="text-right">Прирост</th>
                <th class="text-right">Прирост, %</th>
                <th class="text-right">По рефералам</th>
                <th class="text-right">Всего пользователей</th>
                <th class="text-right">Оплат</th>
                <th class="text-right">Доход</th>
                <th class="text-right">Запуски</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="point in periodRows" :key="point.start">
                <td class="admin-primary">{{ longLabel(point.start) }}</td>
                <td class="text-right tabular-nums admin-primary">{{ point.registrations }}</td>
                <td class="text-right tabular-nums" :class="point.registrations_delta > 0 ? 'admin-up' : point.registrations_delta < 0 ? 'admin-down' : 'muted'">
                  {{ signed(point.registrations_delta, count) }}
                </td>
                <td class="text-right tabular-nums" :class="(point.registrations_delta_pct || 0) > 0 ? 'admin-up' : (point.registrations_delta_pct || 0) < 0 ? 'admin-down' : 'muted'">
                  {{ percent(point.registrations_delta_pct) || '—' }}
                </td>
                <td class="text-right tabular-nums">{{ point.referral_registrations }}</td>
                <td class="text-right tabular-nums">{{ count(point.users_total) }}</td>
                <td class="text-right tabular-nums">{{ point.payments }}</td>
                <td class="text-right tabular-nums">{{ money(point.revenue) }}</td>
                <td class="text-right tabular-nums">{{ point.runs }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
