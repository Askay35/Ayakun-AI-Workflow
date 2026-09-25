<script setup lang="ts">
import type { Plan } from '~/types/api'
import { formatCredits, formatStorage, sortCreditPacks } from '~/utils/credits'
import { apiErrorMessage } from '~/composables/useApi'

definePageMeta({ layout: 'app' })
const api = useApi()
const auth = useAuth()
const toast = useToast()
const { t, locale, formatDate, formatDateOnly } = useI18n()
const [{ data: summary }, { data: plans }, { data: subscription }] = await Promise.all([
  useAuthAsyncData('billing', () => api.billing.summary()),
  useAuthAsyncData('billing-plans', () => api.billing.plans()),
  useAuthAsyncData('billing-subscription', () => api.billing.subscription().catch(() => null))
])
const orderedPlans = computed(() => sortCreditPacks(plans.value || []))
const featuredCode = 'pro'
const active = computed(() => subscription.value?.status === 'active')
const currentPlan = computed(() => (active.value ? subscription.value?.plan : null) || null)
const currentPrice = computed(() => Number(currentPlan.value?.price || 0))
const daysLeft = computed(() => {
  const expires = subscription.value?.expires_at
  if (!active.value || !expires) return 0
  return Math.max(0, Math.ceil((new Date(expires).getTime() - Date.now()) / 86_400_000))
})
const storage = computed(() => subscription.value?.storage)
const percent = (used = 0, max = 0) => (max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0)

type PlanAction = { label: string; disabled: boolean; note?: string; variant: 'solid' | 'outline' | 'soft' }
const planAction = (plan: Plan): PlanAction => {
  const price = Number(plan.price)
  if (!price) {
    return { label: currentPlan.value ? t('billing.downgradeLocked') : t('billing.freeCurrent'), disabled: true, variant: 'outline' }
  }
  if (!currentPlan.value) return { label: t('billing.connect'), disabled: false, variant: 'solid' }
  if (plan.id === currentPlan.value.id) return { label: t('billing.renew'), disabled: false, variant: 'soft' }
  if (price > currentPrice.value) {
    return { label: t('billing.upgrade', { name: plan.name }), disabled: false, note: t('billing.upgradeNote'), variant: 'solid' }
  }
  return { label: t('billing.downgradeLocked'), disabled: true, variant: 'outline' }
}

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
    toast.add({ title: t('billing.payError'), description: apiErrorMessage(error), color: 'error' })
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
    toast.add({ title: t('billing.emailRequired'), description: t('billing.emailHint'), color: 'error' })
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
        <p class="eyebrow">{{ t('billing.eyebrow') }}</p>
        <h1 class="page-title">{{ t('billing.title') }}</h1>
        <p class="muted">{{ t('billing.lead') }}</p>
      </div>
    </div>
    <div class="grid gap-4 lg:grid-cols-3">
      <div class="panel metric-card" style="--card-accent:#6d4aff">
        <span class="metric-icon"><UIcon name="i-lucide-rocket" class="size-6" /></span>
        <div class="min-w-0">
          <p class="mb-0 text-sm font-semibold muted">{{ t('billing.currentPlan') }}</p>
          <p class="metric-value">{{ currentPlan?.name || t('billing.freePlan') }}</p>
          <p v-if="active && subscription?.expires_at" class="mb-0 mt-1 text-xs muted">
            {{ t('billing.activeUntil', { date: formatDateOnly(subscription.expires_at) }) }} · {{ t('billing.daysLeft', { n: daysLeft }) }}
          </p>
          <p v-else-if="subscription?.status === 'expired'" class="mb-0 mt-1 text-xs text-[#c2410c]">{{ t('billing.expiredNote') }}</p>
          <p v-else class="mb-0 mt-1 text-xs muted">{{ t('billing.noPlanNote') }}</p>
        </div>
      </div>
      <div class="panel metric-card" style="--card-accent:#12a67a">
        <span class="metric-icon"><UIcon name="i-lucide-wallet" class="size-6" /></span>
        <div>
          <p class="mb-0 text-sm font-semibold muted">{{ t('billing.onBalance') }}</p>
          <p class="metric-value">{{ formatCredits(summary?.balance) }}</p>
          <p class="mb-0 mt-1 text-xs muted">
            {{ active && subscription?.expires_at ? t('billing.expiresNote', { date: formatDateOnly(subscription.expires_at) }) : t('billing.forRuns') }}
          </p>
        </div>
      </div>
      <div class="panel metric-card" style="--card-accent:#e58a0b">
        <span class="metric-icon"><UIcon name="i-lucide-trending-down" class="size-6" /></span>
        <div>
          <p class="mb-0 text-sm font-semibold muted">{{ t('billing.spentMonth') }}</p>
          <p class="metric-value">{{ formatCredits(summary?.usage_this_month) }}</p>
          <p class="mb-0 mt-1 text-xs muted">{{ t('common.tokens') }}</p>
        </div>
      </div>
    </div>

    <div v-if="storage" class="panel mt-4 p-6">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h2 class="mb-0 text-lg font-extrabold tracking-tight">{{ t('billing.storageTitle') }}</h2>
        <p class="mb-0 text-xs muted">{{ t('billing.storageHint') }}</p>
      </div>
      <div class="mt-4 grid gap-5 md:grid-cols-2">
        <div>
          <div class="mb-2 flex justify-between text-sm font-semibold">
            <span>{{ t('billing.storageFiles') }}</span>
            <span class="muted">{{ storage.files }} / {{ storage.max_files }}</span>
          </div>
          <div class="usage-bar" :class="{ 'is-full': percent(storage.files, storage.max_files) >= 90 }">
            <span :style="{ width: `${percent(storage.files, storage.max_files)}%` }" />
          </div>
        </div>
        <div>
          <div class="mb-2 flex justify-between text-sm font-semibold">
            <span>{{ t('billing.storageSize') }}</span>
            <span class="muted">{{ formatStorage(storage.bytes, locale) }} / {{ formatStorage(storage.max_bytes, locale) }}</span>
          </div>
          <div class="usage-bar" :class="{ 'is-full': percent(storage.bytes, storage.max_bytes) >= 90 }">
            <span :style="{ width: `${percent(storage.bytes, storage.max_bytes)}%` }" />
          </div>
        </div>
      </div>
    </div>

    <div class="mb-4 mt-10">
      <h2 class="mb-1 text-2xl font-extrabold tracking-tight">{{ t('billing.plansTitle') }}</h2>
      <p class="mb-0 muted">{{ t('billing.plansLead') }}</p>
    </div>
    <div class="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      <PlanCard
        v-for="(plan, index) in orderedPlans"
        :key="plan.id"
        :plan="plan"
        :featured="plan.code === featuredCode"
        :top="index === orderedPlans.length - 1"
        :current="currentPlan ? plan.id === currentPlan.id : !Number(plan.price)"
      >
        <UButton
          :label="planAction(plan).label"
          block
          size="lg"
          class="credit-pack-cta"
          :color="plan.code === featuredCode || planAction(plan).disabled ? 'neutral' : 'primary'"
          :variant="planAction(plan).variant"
          :loading="checkoutBusy === plan.id"
          :disabled="planAction(plan).disabled || checkoutBusy === plan.id"
          @click="startCheckout(plan.id)"
        />
        <p v-if="planAction(plan).note" class="plan-card-note">{{ planAction(plan).note }}</p>
      </PlanCard>
    </div>
    <UModal
      :open="emailModalOpen"
      :title="t('billing.emailTitle')"
      :description="t('billing.emailDesc')"
      :dismissible="checkoutBusy == null"
      :ui="{ footer: 'justify-end' }"
      @update:open="onEmailModalOpen"
    >
      <template #body>
        <form class="space-y-4" @submit.prevent="confirmReceiptEmail">
          <UFormField label="Email">
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
        <UButton :label="t('common.cancel')" color="neutral" variant="outline" :disabled="checkoutBusy != null" @click="close" />
        <UButton :label="t('billing.payGo')" :loading="checkoutBusy != null" @click="confirmReceiptEmail" />
      </template>
    </UModal>
    <div class="panel mt-8 p-6">
      <h2 class="mb-1 text-xl font-extrabold tracking-tight">{{ t('billing.history') }}</h2>
      <p class="mb-4 text-sm muted">{{ t('billing.historyLead') }}</p>
      <div v-if="summary?.ledger?.length" class="row-list mt-3">
        <div v-for="entry in summary.ledger" :key="entry.id" class="flex justify-between gap-4 py-3">
          <div>
            <p class="mb-0 font-medium">{{ entry.description }}</p>
            <p class="mb-0 mt-1 text-xs muted">{{ formatDate(entry.created_at) }}</p>
          </div>
          <strong class="shrink-0" :class="entry.amount > 0 ? 'text-[#15803d]' : 'text-[#c2410c]'">
            {{ entry.amount > 0 ? '+' : '' }}{{ formatCredits(entry.amount) }}
          </strong>
        </div>
      </div>
      <p v-else class="mb-0 mt-3 text-sm muted">{{ t('billing.empty') }}</p>
    </div>
  </div>
</template>
