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

export function bestValuePackCode(plans: Array<{ code: string; price: number; limits?: { included_credits?: number } | Record<string, number> }>) {
  let code: string | undefined
  let best = 0
  for (const plan of plans) {
    const price = Number(plan.price)
    if (!price) continue
    const rate = packCredits(plan) / price
    if (rate > best) {
      best = rate
      code = plan.code
    }
  }
  return code
}
