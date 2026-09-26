import type { SearchPeriod } from '~/types/api'
import { newSlotId, type ScheduleSlot } from '~/utils/schedule'

export type OnboardingFrequency = 'hourly' | 'daily' | 'weekdays' | 'weekly' | 'manual'

/** Цель ведёт на линейный шаблон: его можно открыть и на телефоне. event — запуск по вебхуку, частота не нужна. */
export type OnboardingGoal = { key: string; icon: string; template: string; trigger?: 'event' }
export type OnboardingRole = { key: string; icon: string; goals: OnboardingGoal[] }

export const ONBOARDING_ROLES: OnboardingRole[] = [
  {
    key: 'marketing',
    icon: 'i-lucide-megaphone',
    goals: [
      { key: 'trends', icon: 'i-lucide-newspaper', template: 'news-digest-telegram' },
      { key: 'posts', icon: 'i-lucide-pen-line', template: 'telegram-channel-post' },
      { key: 'images', icon: 'i-lucide-image', template: 'image-of-the-day' },
      { key: 'competitors', icon: 'i-lucide-radar', template: 'competitor-news-digest' }
    ]
  },
  {
    key: 'sales',
    icon: 'i-lucide-handshake',
    goals: [
      { key: 'leads', icon: 'i-lucide-inbox', template: 'lead-to-sheets-telegram', trigger: 'event' },
      { key: 'tenders', icon: 'i-lucide-target', template: 'tenders-digest' },
      { key: 'clients', icon: 'i-lucide-user-search', template: 'client-research' },
      { key: 'competitors', icon: 'i-lucide-radar', template: 'competitor-news-digest' }
    ]
  },
  {
    key: 'ecommerce',
    icon: 'i-lucide-shopping-bag',
    goals: [
      { key: 'prices', icon: 'i-lucide-tags', template: 'competitor-prices-digest' },
      { key: 'reviews', icon: 'i-lucide-message-square-text', template: 'reviews-digest' },
      { key: 'descriptions', icon: 'i-lucide-camera', template: 'photo-description' },
      { key: 'trends', icon: 'i-lucide-newspaper', template: 'news-digest-telegram' }
    ]
  },
  {
    key: 'it',
    icon: 'i-lucide-code-xml',
    goals: [
      { key: 'stack', icon: 'i-lucide-cpu', template: 'tech-news-digest' },
      { key: 'standup', icon: 'i-lucide-kanban', template: 'jira-standup-slack' },
      { key: 'releases', icon: 'i-lucide-rocket', template: 'release-notes-slack' },
      { key: 'bugs', icon: 'i-lucide-bug', template: 'bug-report-to-jira', trigger: 'event' }
    ]
  },
  {
    key: 'business',
    icon: 'i-lucide-briefcase-business',
    goals: [
      { key: 'salesReport', icon: 'i-lucide-chart-column', template: 'daily-sales-report' },
      { key: 'currency', icon: 'i-lucide-banknote', template: 'currency-rates-daily' },
      { key: 'laws', icon: 'i-lucide-scale', template: 'business-law-digest' },
      { key: 'competitors', icon: 'i-lucide-radar', template: 'competitor-news-digest' }
    ]
  },
  {
    key: 'personal',
    icon: 'i-lucide-graduation-cap',
    goals: [
      { key: 'learning', icon: 'i-lucide-book-open', template: 'daily-lesson' },
      { key: 'jobs', icon: 'i-lucide-briefcase', template: 'vacancies-digest' },
      { key: 'events', icon: 'i-lucide-ticket', template: 'city-events-digest' },
      { key: 'news', icon: 'i-lucide-newspaper', template: 'news-digest-telegram' }
    ]
  }
]

export const ONBOARDING_FREQUENCIES: Array<{ key: OnboardingFrequency; icon: string }> = [
  { key: 'hourly', icon: 'i-lucide-zap' },
  { key: 'daily', icon: 'i-lucide-sun' },
  { key: 'weekdays', icon: 'i-lucide-calendar-range' },
  { key: 'weekly', icon: 'i-lucide-calendar-days' },
  { key: 'manual', icon: 'i-lucide-hand' }
]

export const ONBOARDING_TIMES = ['08:00', '09:00', '12:00', '18:00', '21:00']

/** Частота из опроса → слоты автозапуска и глубина поиска, чтобы в выдаче были только новые материалы. */
export function scheduleForFrequency(frequency: OnboardingFrequency, time: string): { slots: ScheduleSlot[]; period: SearchPeriod | null } {
  if (frequency === 'hourly') return { slots: [{ id: newSlotId(), kind: 'interval', every: 1, unit: 'hours' }], period: 'd' }
  if (frequency === 'daily') return { slots: [{ id: newSlotId(), kind: 'weekly', time, weekdays: [1, 2, 3, 4, 5, 6, 7] }], period: 'd' }
  if (frequency === 'weekdays') return { slots: [{ id: newSlotId(), kind: 'weekly', time, weekdays: [1, 2, 3, 4, 5] }], period: 'd' }
  if (frequency === 'weekly') return { slots: [{ id: newSlotId(), kind: 'weekly', time, weekdays: [1] }], period: 'w' }
  return { slots: [], period: null }
}
