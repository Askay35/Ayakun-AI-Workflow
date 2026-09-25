export function creditsAmount(value?: number | string | null) {
  const amount = Number(value || 0)
  if (!Number.isFinite(amount)) return 0
  return amount
}

export function formatCredits(value?: number | string | null) {
  return creditsAmount(value).toLocaleString('ru-RU', { maximumFractionDigits: 4 })
}

export function packCredits(plan: { limits?: { included_credits?: number } | Record<string, number> }) {
  return creditsAmount(plan.limits?.included_credits)
}

export function sortCreditPacks<T extends { price: number; limits?: { included_credits?: number } | Record<string, number> }>(plans: T[]) {
  return [...plans].sort((a, b) => Number(a.price) - Number(b.price) || packCredits(a) - packCredits(b))
}

export function formatStorage(bytes: number, locale: 'ru' | 'en' = 'ru') {
  const gb = bytes / 1024 ** 3
  if (gb >= 1) return `${Number(gb.toFixed(gb >= 10 ? 0 : 1)).toLocaleString(locale)} ${locale === 'en' ? 'GB' : 'ГБ'}`
  const mb = bytes / 1024 ** 2
  return `${Number(mb.toFixed(mb >= 10 ? 0 : 1)).toLocaleString(locale)} ${locale === 'en' ? 'MB' : 'МБ'}`
}

export function planStorageBytes(plan: { limits?: Record<string, number> }) {
  return Number(plan.limits?.max_storage_mb || 0) * 1024 ** 2
}
