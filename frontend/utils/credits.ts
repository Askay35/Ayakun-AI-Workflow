export function creditsAmount(value?: number | string | null) {
  const amount = Number(value || 0)
  if (!Number.isFinite(amount)) return 0
  return amount
}

export function formatCredits(value?: number | string | null) {
  return creditsAmount(value).toLocaleString('ru-RU', { maximumFractionDigits: 4 })
}
