import { en } from '~/i18n/en'
import { ru } from '~/i18n/ru'

export type AppLocale = 'ru' | 'en'

const messages = { ru, en } as const

function lookup(source: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (acc && typeof acc === 'object' && key in acc) return (acc as Record<string, unknown>)[key]
    return undefined
  }, source)
}

function interpolate(text: string, vars?: Record<string, string | number>) {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (_, key: string) => (
    Object.prototype.hasOwnProperty.call(vars, key) ? String(vars[key]) : `{${key}}`
  ))
}

export function useI18n() {
  const locale = useCookie<AppLocale>('ayakun_locale', {
    default: () => 'ru',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 365
  })

  if (locale.value !== 'en' && locale.value !== 'ru') locale.value = 'ru'

  const dict = computed(() => messages[locale.value || 'ru'])
  const dateLocale = computed(() => (locale.value === 'en' ? 'en-GB' : 'ru-RU'))

  const t = (path: string, vars?: Record<string, string | number>) => {
    const value = lookup(dict.value, path)
    if (typeof value !== 'string') return path
    return interpolate(value, vars)
  }

  const tm = <T = unknown>(path: string): T => {
    const value = lookup(dict.value, path)
    return (value ?? []) as T
  }

  const setLocale = (next: AppLocale) => {
    locale.value = next
  }

  const formatDate = (value: string | number | Date, options?: Intl.DateTimeFormatOptions) => (
    new Date(value).toLocaleString(dateLocale.value, options)
  )

  const formatDateOnly = (value: string | number | Date) => (
    new Date(value).toLocaleDateString(dateLocale.value)
  )

  const formatMoney = (value: number) => (
    value.toLocaleString(dateLocale.value)
  )

  return { locale, t, tm, setLocale, dateLocale, formatDate, formatDateOnly, formatMoney }
}
