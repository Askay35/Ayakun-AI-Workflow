<script setup lang="ts">
import { apiErrorMessage } from '~/composables/useApi'
import type { WorkflowTemplate } from '~/types/api'
import {
  ONBOARDING_FREQUENCIES,
  ONBOARDING_ROLES,
  ONBOARDING_TIMES,
  scheduleForFrequency,
  type OnboardingFrequency,
  type OnboardingGoal,
  type OnboardingRole
} from '~/utils/onboarding'
import { NODE_META } from '~/utils/workflow-graph'

definePageMeta({ layout: false, middleware: 'auth' })

const api = useApi()
const auth = useAuth()
const toast = useToast()
const { t, locale } = useI18n()
const isMobile = useIsMobileEditor()
useAppTitle(computed(() => t('onboarding.pageTitle')))

const step = ref(0)
const role = ref<OnboardingRole>()
const goal = ref<OnboardingGoal>()
const frequency = ref<OnboardingFrequency>()
const time = ref('09:00')
const building = ref(false)
const buildStage = ref(0)
const skipping = ref(false)

const { data: templates } = await useAuthAsyncData<WorkflowTemplate[]>('onboarding-templates', () => api.templates.list().catch(() => []))
const template = computed(() => templates.value?.find(item => item.slug === goal.value?.template))
const templateName = computed(() => template.value ? (locale.value === 'en' ? template.value.name_en : template.value.name) : '')
const firstName = computed(() => (auth.user.value?.name || '').trim().split(/\s+/)[0] || '')
const needsTime = computed(() => frequency.value && frequency.value !== 'hourly' && frequency.value !== 'manual')
const stepLabels = computed(() => [t('onboarding.progress.role'), t('onboarding.progress.goal'), t('onboarding.progress.frequency')])
const buildStages = computed(() => [t('onboarding.build.template'), t('onboarding.build.schedule'), t('onboarding.build.open')])

const pickRole = (item: OnboardingRole) => {
  if (role.value?.key !== item.key) goal.value = undefined
  role.value = item
  setTimeout(() => { step.value = 1 }, 180)
}

const pickGoal = (item: OnboardingGoal) => {
  goal.value = item
  if (item.trigger === 'event') {
    frequency.value = undefined
    setTimeout(finish, 180)
    return
  }
  setTimeout(() => { step.value = 2 }, 180)
}

const markDone = () => {
  if (auth.user.value) auth.user.value = { ...auth.user.value, onboarded_at: new Date().toISOString() }
}

const finish = async () => {
  if (!role.value || !goal.value || building.value) return
  building.value = true
  buildStage.value = 0
  const timer = setInterval(() => { buildStage.value = Math.min(buildStage.value + 1, 2) }, 650)
  const { slots, period } = scheduleForFrequency(frequency.value || 'manual', time.value)
  try {
    const [result] = await Promise.all([
      api.users.completeOnboarding({
        answers: { role: role.value.key, goal: goal.value.key, frequency: frequency.value || 'event', time: needsTime.value ? time.value : '' },
        template_slug: goal.value.template,
        schedule_slots: slots,
        schedule_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
        search_period: period,
        mobile: isMobile.value
      }),
      // Короткая пауза, чтобы анимация сборки не мелькнула.
      new Promise(resolve => setTimeout(resolve, 1600))
    ])
    markDone()
    await navigateTo(result.workflow_id ? `/workflows/${result.workflow_id}` : '/workflows', { replace: true })
  } catch (error) {
    building.value = false
    toast.add({ title: t('onboarding.buildError'), description: apiErrorMessage(error, t('common.genericError')), color: 'error' })
  } finally {
    clearInterval(timer)
  }
}

const skip = async () => {
  skipping.value = true
  try {
    await api.users.completeOnboarding({
      answers: { role: role.value?.key || '', goal: goal.value?.key || '', skipped: 'true' },
      template_slug: null,
      schedule_slots: [],
      schedule_timezone: 'UTC',
      search_period: null,
      mobile: false
    })
    markDone()
    await navigateTo('/dashboard', { replace: true })
  } catch (error) {
    toast.add({ title: t('common.genericError'), description: apiErrorMessage(error), color: 'error' })
  } finally {
    skipping.value = false
  }
}
</script>

<template>
  <main class="onboarding">
    <div class="onboarding-blob onboarding-blob-a" aria-hidden="true" />
    <div class="onboarding-blob onboarding-blob-b" aria-hidden="true" />

    <header class="onboarding-top">
      <span class="brand">
        <img src="~/assets/images/logo.png" alt="" class="app-logo-mark" width="28" height="28" />
        Ayakun
      </span>
      <button v-if="!building" type="button" class="onboarding-skip" :disabled="skipping" @click="skip">
        {{ t('onboarding.skip') }}
      </button>
    </header>

    <section v-if="building" class="onboarding-card onboarding-building reveal">
      <div class="onboarding-orbit" aria-hidden="true">
        <span class="onboarding-orbit-core"><UIcon name="i-lucide-wand-sparkles" class="size-7" /></span>
      </div>
      <h1 class="onboarding-title">{{ t('onboarding.build.title') }}</h1>
      <p class="onboarding-lead">{{ templateName }}</p>
      <ul class="onboarding-stages">
        <li v-for="(label, index) in buildStages" :key="label" :class="{ done: index < buildStage, active: index === buildStage }">
          <UIcon :name="index < buildStage ? 'i-lucide-circle-check' : 'i-lucide-loader-circle'" class="size-4" :class="{ 'animate-spin': index === buildStage }" />
          {{ label }}
        </li>
      </ul>
    </section>

    <section v-else class="onboarding-card">
      <div class="onboarding-progress" role="progressbar" :aria-valuenow="step + 1" aria-valuemin="1" aria-valuemax="3">
        <button
          v-for="(label, index) in stepLabels"
          :key="label"
          type="button"
          class="onboarding-progress-item"
          :class="{ done: index < step, active: index === step }"
          :disabled="index > step"
          @click="step = index"
        >
          <span class="onboarding-progress-bar" />
          <span class="onboarding-progress-label">{{ label }}</span>
        </button>
      </div>

      <Transition name="onboarding-slide" mode="out-in">
        <div v-if="step === 0" key="role">
          <p class="eyebrow">{{ firstName ? t('onboarding.hello', { name: firstName }) : t('onboarding.helloAnon') }}</p>
          <h1 class="onboarding-title">{{ t('onboarding.role.title') }}</h1>
          <p class="onboarding-lead">{{ t('onboarding.role.lead') }}</p>
          <div class="onboarding-options">
            <button
              v-for="(item, index) in ONBOARDING_ROLES"
              :key="item.key"
              type="button"
              class="onboarding-option"
              :class="{ selected: role?.key === item.key }"
              :style="{ animationDelay: `${index * 45}ms` }"
              @click="pickRole(item)"
            >
              <span class="onboarding-option-icon"><UIcon :name="item.icon" class="size-5" /></span>
              <span class="min-w-0">
                <span class="onboarding-option-title">{{ t(`onboarding.roles.${item.key}.title`) }}</span>
                <span class="onboarding-option-text">{{ t(`onboarding.roles.${item.key}.text`) }}</span>
              </span>
              <UIcon name="i-lucide-check" class="onboarding-option-check size-4" />
            </button>
          </div>
        </div>

        <div v-else-if="step === 1 && role" key="goal">
          <p class="eyebrow">{{ t(`onboarding.roles.${role.key}.title`) }}</p>
          <h1 class="onboarding-title">{{ t('onboarding.goal.title') }}</h1>
          <p class="onboarding-lead">{{ t('onboarding.goal.lead') }}</p>
          <div class="onboarding-options">
            <button
              v-for="(item, index) in role.goals"
              :key="item.key"
              type="button"
              class="onboarding-option"
              :class="{ selected: goal?.key === item.key }"
              :style="{ animationDelay: `${index * 45}ms` }"
              @click="pickGoal(item)"
            >
              <span class="onboarding-option-icon"><UIcon :name="item.icon" class="size-5" /></span>
              <span class="min-w-0">
                <span class="onboarding-option-title">{{ t(`onboarding.goals.${item.key}.title`) }}</span>
                <span class="onboarding-option-text">{{ t(`onboarding.goals.${item.key}.text`) }}</span>
              </span>
              <UIcon name="i-lucide-check" class="onboarding-option-check size-4" />
            </button>
          </div>
          <button type="button" class="onboarding-back" @click="step = 0">
            <UIcon name="i-lucide-arrow-left" class="size-4" /> {{ t('onboarding.back') }}
          </button>
        </div>

        <div v-else-if="step === 2 && goal" key="frequency">
          <p class="eyebrow">{{ t(`onboarding.goals.${goal.key}.title`) }}</p>
          <h1 class="onboarding-title">{{ t('onboarding.frequency.title') }}</h1>
          <p class="onboarding-lead">{{ t('onboarding.frequency.lead') }}</p>
          <div v-if="template" class="onboarding-preview">
            <span class="onboarding-preview-label">{{ t('onboarding.picked') }}</span>
            <strong>{{ templateName }}</strong>
            <div class="template-chain !mt-2 !border-0 !pt-0">
              <template v-for="(item, index) in template.steps" :key="index">
                <span
                  class="template-chain-icon"
                  :title="item.label"
                  :style="{ color: NODE_META[item.type]?.accent, background: `${NODE_META[item.type]?.accent}1a` }"
                >
                  <UIcon :name="NODE_META[item.type]?.icon || 'i-lucide-box'" class="size-3.5" />
                </span>
                <UIcon v-if="index < template.steps.length - 1" name="i-lucide-chevron-right" class="template-chain-arrow" />
              </template>
            </div>
          </div>
          <div class="onboarding-options is-compact">
            <button
              v-for="(item, index) in ONBOARDING_FREQUENCIES"
              :key="item.key"
              type="button"
              class="onboarding-option"
              :class="{ selected: frequency === item.key }"
              :style="{ animationDelay: `${index * 45}ms` }"
              @click="frequency = item.key"
            >
              <span class="onboarding-option-icon"><UIcon :name="item.icon" class="size-5" /></span>
              <span class="min-w-0">
                <span class="onboarding-option-title">{{ t(`onboarding.freq.${item.key}.title`) }}</span>
                <span class="onboarding-option-text">{{ t(`onboarding.freq.${item.key}.text`) }}</span>
              </span>
              <UIcon name="i-lucide-check" class="onboarding-option-check size-4" />
            </button>
          </div>
          <Transition name="onboarding-fade">
            <div v-if="needsTime" class="onboarding-times">
              <span class="onboarding-times-label"><UIcon name="i-lucide-clock-3" class="size-4" /> {{ t('onboarding.time') }}</span>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="value in ONBOARDING_TIMES"
                  :key="value"
                  type="button"
                  class="onboarding-time"
                  :class="{ selected: time === value }"
                  @click="time = value"
                >
                  {{ value }}
                </button>
              </div>
            </div>
          </Transition>
          <div class="onboarding-actions">
            <button type="button" class="onboarding-back" @click="step = 1">
              <UIcon name="i-lucide-arrow-left" class="size-4" /> {{ t('onboarding.back') }}
            </button>
            <button type="button" class="site-button large" :disabled="!frequency" @click="finish">
              {{ t('onboarding.build.cta') }}
              <UIcon name="i-lucide-arrow-right" />
            </button>
          </div>
        </div>
      </Transition>
    </section>
  </main>
</template>
