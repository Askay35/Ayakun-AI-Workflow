export type IntervalUnit = 'minutes' | 'hours' | 'days'

export type WeeklyScheduleSlot = {
  id: string
  kind: 'weekly'
  time: string
  weekdays: number[]
  next_at?: string | null
}

export type IntervalScheduleSlot = {
  id: string
  kind: 'interval'
  every: number
  unit: IntervalUnit
  next_at?: string | null
}

export type ScheduleSlot = WeeklyScheduleSlot | IntervalScheduleSlot

export const WEEKDAY_OPTIONS = [
  { label: 'Пн', value: 1 },
  { label: 'Вт', value: 2 },
  { label: 'Ср', value: 3 },
  { label: 'Чт', value: 4 },
  { label: 'Пт', value: 5 },
  { label: 'Сб', value: 6 },
  { label: 'Вс', value: 7 }
] as const

export const INTERVAL_UNITS: Array<{ label: string; value: IntervalUnit }> = [
  { label: 'минут', value: 'minutes' },
  { label: 'часов', value: 'hours' },
  { label: 'дней', value: 'days' }
]

const WEEKDAY_LABEL = Object.fromEntries(WEEKDAY_OPTIONS.map(item => [item.value, item.label]))

export function newSlotId() {
  return crypto.randomUUID().replace(/-/g, '').slice(0, 12)
}

export function parseCronToWeekly(cron?: string | null): WeeklyScheduleSlot | null {
  if (!cron) return null
  const [minute = '0', hour = '9', , , rawDays = '*'] = cron.split(/\s+/)
  if (!/^\d+$/.test(minute) || !/^\d+$/.test(hour)) return null
  const weekdays = rawDays === '*'
    ? [1, 2, 3, 4, 5, 6, 7]
    : rawDays.split(',').map(Number).map(day => day === 0 ? 7 : day).filter(day => day >= 1 && day <= 7)
  if (!weekdays.length) return null
  return {
    id: newSlotId(),
    kind: 'weekly',
    time: `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`,
    weekdays
  }
}

export function slotsFromWorkflow(input: { schedule_slots?: ScheduleSlot[] | null; schedule_cron?: string | null }) {
  const stored = (input.schedule_slots || []).filter(slot => slot?.kind === 'weekly' || slot?.kind === 'interval')
  if (stored.length) {
    return stored.map(slot => ({
      ...slot,
      id: slot.id || newSlotId()
    })) as ScheduleSlot[]
  }
  const weekly = parseCronToWeekly(input.schedule_cron)
  return weekly ? [weekly] : []
}

export function slotKey(slot: ScheduleSlot) {
  return slot.kind === 'weekly'
    ? `weekly:${slot.time}:${slot.weekdays.join(',')}`
    : `interval:${slot.every}:${slot.unit}`
}

export function formatSlot(slot: ScheduleSlot) {
  if (slot.kind === 'weekly') {
    const days = slot.weekdays.map(day => WEEKDAY_LABEL[day] || day).join(', ')
    return `${days} · ${slot.time}`
  }
  const unit = INTERVAL_UNITS.find(item => item.value === slot.unit)?.label || slot.unit
  return `Каждые ${slot.every} ${unit}`
}

export function slotCaption(slot: ScheduleSlot) {
  return slot.kind === 'weekly' ? 'По дням' : 'Интервал'
}
