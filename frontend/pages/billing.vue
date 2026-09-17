<script setup lang="ts">
import { bestValuePackCode, formatCredits, packCredits, sortCreditPacks } from '~/utils/credits'
import { apiErrorMessage } from '~/composables/useApi'

definePageMeta({ layout: 'app' })
const api = useApi()
const auth = useAuth()
const toast = useToast()
const [{ data: summary }, { data: plans }] = await Promise.all([
  useAuthAsyncData('billing', () => api.billing.summary()),
  useAuthAsyncData('billing-plans', () => api.billing.plans())
])
const orderedPlans = computed(() => sortCreditPacks(plans.value || []))
const featuredCode = computed(() => bestValuePackCode(orderedPlans.value))
const checkoutKeys = new Map<number, string>()
const checkoutBusy = ref<number | null>(null)
const emailModalOpen = ref(false)
const pendingPlanId = ref<number | null>(null)
const receiptEmail = ref('')
const profileEmail = computed(() => auth.user.value?.email?.trim() || '')

const checkout = async (planId: number, customerEmail?: string) => {
  if (checkoutBusy.value === planId) return
  checkoutBusy.value = planId
  const key = checkoutKeys.get(planId) ?? crypto.randomUUID()
  checkoutKeys.set(planId, key)
  try {
    const { confirmation_url } = await api.billing.checkout(planId, key, customerEmail)
    if (auth.user.value && customerEmail && !auth.user.value.email) {
      auth.user.value = { ...auth.user.value, email: customerEmail.trim().toLowerCase() }
    }
    if (confirmation_url) location.href = confirmation_url
  } catch (error: any) {
    checkoutKeys.delete(planId)
    toast.add({ title: 'Оплата недоступна', description: apiErrorMessage(error), color: 'error' })
  } finally {
    checkoutBusy.value = null
  }
}

const startCheckout = (planId: number) => {
  const email = profileEmail.value || receiptEmail.value.trim()
  if (email) {
    checkout(planId, email)
    return
  }
  pendingPlanId.value = planId
  emailModalOpen.value = true
}

const confirmReceiptEmail = () => {
  const email = receiptEmail.value.trim()
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    toast.add({ title: 'Укажите email', description: 'Нужен адрес, куда отправить чек.', color: 'error' })
    return
  }
  if (pendingPlanId.value == null) return
  checkout(pendingPlanId.value, email)
}

const onEmailModalOpen = (open: boolean) => {
  emailModalOpen.value = open
  if (!open && checkoutBusy.value == null) pendingPlanId.value = null
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <p class="eyebrow">Баланс</p>
        <h1 class="page-title">Пополнение credits</h1>
        <p class="muted">Пакет credits — разовая покупка. Списывается фактический расход запуска, остаток не сгорает.</p>
      </div>
    </div>
    <div class="grid-cards">
      <div class="panel metric-card" style="--card-accent:#c9f169"><p class="mb-0 text-sm font-bold muted">На балансе</p><p class="metric-value">{{ formatCredits(summary?.balance) }}</p><p class="mb-0 mt-1 text-xs muted">credits для запусков</p></div>
      <div class="panel metric-card" style="--card-accent:#ffb681"><p class="mb-0 text-sm font-bold muted">Потрачено за месяц</p><p class="metric-value">{{ formatCredits(summary?.usage_this_month) }}</p><p class="mb-0 mt-1 text-xs muted">credits</p></div>
    </div>
    <div class="mb-4 mt-10"><h2 class="mb-1 text-2xl font-extrabold">Пополнить баланс</h2><p class="mb-0 muted">Цена пакета = число credits. В редакторе до запуска виден максимум списания.</p></div>
    <div class="grid-cards">
      <div
        v-for="plan in orderedPlans"
        :key="plan.id"
        class="panel credit-pack"
        :class="{
          'is-gift': !Number(plan.price),
          'is-featured': plan.code === featuredCode
        }"
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
          :label="Number(plan.price) ? 'Купить' : 'Уже на старте'"
          block
          size="lg"
          class="credit-pack-cta mt-auto"
          :color="plan.code === featuredCode ? 'neutral' : 'primary'"
          :variant="Number(plan.price) ? 'solid' : 'outline'"
          :loading="checkoutBusy === plan.id"
          :disabled="!Number(plan.price) || checkoutBusy === plan.id"
          @click="startCheckout(plan.id)"
        />
      </div>
    </div>
    <UModal
      :open="emailModalOpen"
      title="Email для чека"
      description="Укажите почту для чека — она сохранится в профиле."
      :dismissible="checkoutBusy == null"
      :ui="{ footer: 'justify-end' }"
      @update:open="onEmailModalOpen"
    >
      <template #body>
        <form class="space-y-4" @submit.prevent="confirmReceiptEmail">
          <UFormField label="Email" :ui="{ label: 'text-white!' }">
            <UInput
              v-model="receiptEmail"
              type="email"
              autocomplete="email"
              placeholder="name@example.com"
              size="lg"
              class="w-full"
              autofocus
            />
          </UFormField>
        </form>
      </template>
      <template #footer="{ close }">
        <UButton label="Отмена" color="neutral" variant="outline" :disabled="checkoutBusy != null" @click="close" />
        <UButton label="Перейти к оплате" :loading="checkoutBusy != null" @click="confirmReceiptEmail" />
      </template>
    </UModal>
    <div class="panel mt-8 p-6">
      <h2 class="mb-1 text-xl font-extrabold">История баланса</h2>
      <p class="mb-4 text-sm muted">Пополнения и фактические списания за звенья. Резерв на время запуска в историю не попадает.</p>
      <div v-if="summary?.ledger?.length" class="mt-3 divide-y divide-default">
        <div v-for="entry in summary.ledger" :key="entry.id" class="flex justify-between gap-4 py-3">
          <div>
            <p class="mb-0 font-medium">{{ entry.description }}</p>
            <p class="mb-0 mt-1 text-xs muted">{{ new Date(entry.created_at).toLocaleString('ru') }}</p>
          </div>
          <strong class="shrink-0" :class="entry.amount > 0 ? 'text-[#4b3dcc]' : 'text-[#c45c3e]'">
            {{ entry.amount > 0 ? '+' : '' }}{{ formatCredits(entry.amount) }}
          </strong>
        </div>
      </div>
      <p v-else class="mb-0 mt-3 text-sm muted">Пока нет операций с балансом.</p>
    </div>
  </div>
</template>
