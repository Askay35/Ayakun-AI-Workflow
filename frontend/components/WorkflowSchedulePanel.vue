<script setup lang="ts">
import {
  INTERVAL_UNITS as UNIT_VALUES,
  newSlotId,
  slotKey,
  type IntervalUnit,
  type ScheduleSlot
} from '~/utils/schedule'

const props = defineProps<{
  enabled: boolean
  slots: ScheduleSlot[]
  timezone: string
}>()

const emit = defineEmits<{
  'update:enabled': [value: boolean]
  'update:slots': [value: ScheduleSlot[]]
}>()

const { t } = useI18n()
const draftKind = ref<'weekly' | 'interval'>('weekly')
const draftTime = ref('09:00')
const draftDays = ref<number[]>([1, 2, 3, 4, 5])
const draftEvery = ref(30)
const draftUnit = ref<IntervalUnit>('minutes')
const formError = ref('')

const weekdayOptions = computed(() => (
  [1, 2, 3, 4, 5, 6, 7].map(value => ({ value, label: t(`schedule.days.${value}`) }))
))
const intervalUnits = computed(() => (
  UNIT_VALUES.map(item => ({ value: item.value, label: t(`schedule.units.${item.value}`) }))
))

const weeklyValid = computed(() => /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(draftTime.value) && draftDays.value.length > 0)
const intervalValid = computed(() => Number(draftEvery.value) >= 1)
const canAdd = computed(() => draftKind.value === 'weekly' ? weeklyValid.value : intervalValid.value)

const formatSlotLabel = (slot: ScheduleSlot) => {
  if (slot.kind === 'weekly') {
    const days = slot.weekdays.map(day => t(`schedule.days.${day}`)).join(', ')
    return `${days} · ${slot.time}`
  }
  return t('schedule.everyLabel', { every: slot.every, unit: t(`schedule.units.${slot.unit}`) })
}

const toggleDay = (day: number) => {
  draftDays.value = draftDays.value.includes(day)
    ? draftDays.value.filter(value => value !== day)
    : [...draftDays.value, day].sort((a, b) => a - b)
}

const addSlot = () => {
  formError.value = ''
  const next = draftKind.value === 'weekly'
    ? {
        id: newSlotId(),
        kind: 'weekly' as const,
        time: draftTime.value,
        weekdays: [...draftDays.value]
      }
    : {
        id: newSlotId(),
        kind: 'interval' as const,
        every: Math.max(1, Math.round(Number(draftEvery.value) || 1)),
        unit: draftUnit.value
      }
  if (props.slots.some(slot => slotKey(slot) === slotKey(next))) {
    formError.value = t('schedule.duplicate')
    return
  }
  emit('update:slots', [...props.slots, next])
}

const removeSlot = (id: string) => {
  emit('update:slots', props.slots.filter(slot => slot.id !== id))
}
</script>

<template>
  <div class="editor-schedule">
    <div class="flex items-center justify-between gap-2">
      <p class="mb-0 text-sm font-extrabold text-white">{{ t('schedule.title') }}</p>
      <USwitch :model-value="enabled" @update:model-value="emit('update:enabled', $event)" />
    </div>
    <p class="mb-0 text-[11px] leading-5 text-white/40">{{ t('schedule.hint') }}</p>

    <div v-if="slots.length" class="schedule-slot-list">
      <div v-for="slot in slots" :key="slot.id" class="schedule-slot">
        <span class="schedule-slot-kind">{{ slot.kind === 'weekly' ? t('schedule.weekly') : t('schedule.interval') }}</span>
        <strong class="schedule-slot-title">{{ formatSlotLabel(slot) }}</strong>
        <button type="button" class="schedule-slot-remove" :aria-label="t('schedule.remove')" @click="removeSlot(slot.id)">
          <UIcon name="i-lucide-x" class="size-3.5" />
        </button>
      </div>
    </div>
    <template v-if="enabled">
      <div class="schedule-kind">
        <button type="button" class="schedule-kind-btn" :class="{ 'is-active': draftKind === 'weekly' }" @click="draftKind = 'weekly'">{{ t('schedule.weekly') }}</button>
        <button type="button" class="schedule-kind-btn" :class="{ 'is-active': draftKind === 'interval' }" @click="draftKind = 'interval'">{{ t('schedule.interval') }}</button>
      </div>

      <template v-if="draftKind === 'weekly'">
        <UFormField :label="t('schedule.time')">
          <UInput v-model="draftTime" type="time" class="w-full" />
        </UFormField>
        <div>
          <p class="mb-2 text-[11px] font-bold text-white/60">{{ t('schedule.weekdays') }}</p>
          <div class="grid grid-cols-4 gap-1.5">
            <button
              v-for="day in weekdayOptions"
              :key="day.value"
              type="button"
              class="schedule-day"
              :class="{ 'is-active': draftDays.includes(day.value) }"
              @click="toggleDay(day.value)"
            >
              {{ day.label }}
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="grid grid-cols-[1fr_1.2fr] gap-2">
          <UFormField :label="t('schedule.every')">
            <UInput v-model.number="draftEvery" type="number" min="1" class="schedule-every w-full" />
          </UFormField>
          <UFormField :label="t('schedule.unit')">
            <USelect v-model="draftUnit" :items="intervalUnits" value-key="value" class="w-full" />
          </UFormField>
        </div>
      </template>

      <p v-if="formError" class="mb-0 text-[11px] text-red-300">{{ formError }}</p>
      <UButton
        :label="t('schedule.add')"
        icon="i-lucide-plus"
        color="neutral"
        variant="soft"
        block
        :disabled="!canAdd"
        class="schedule-add"
        @click="addSlot"
      />
      <p class="mb-0 text-[10px] text-white/35">{{ t('schedule.timezone', { tz: timezone }) }}</p>
    </template>
  </div>
</template>
