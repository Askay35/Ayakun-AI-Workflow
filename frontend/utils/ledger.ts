/** Операции, которые меняют баланс с точки зрения пользователя. */
const VISIBLE_LEDGER_KINDS = new Set(['credit', 'purchase', 'charge', 'refund'])

type LedgerItem = {
  id: string
  created_at: string
  amount: number
  kind: string
  reference?: string | null
  metadata_?: Record<string, unknown> | null
}

function shortRunId(reference?: string | null) {
  if (!reference) return ''
  const id = reference.replace(/^run:/, '')
  return id.length > 8 ? id.slice(0, 8) : id
}

function chargeLabel(item: LedgerItem) {
  const meta = item.metadata_ || (item as { metadata?: Record<string, unknown> }).metadata || {}
  const provider = String(meta.provider || '')
  const model = String(meta.model || '')
  const run = shortRunId(item.reference)
  const what =
    provider === 'serper' ? 'поиск'
      : provider === 'deepseek' || provider === 'qwen' ? `AI (${model || provider})`
        : provider === 'telegram' ? 'Telegram'
          : 'запуск'
  return run ? `Списание · ${what} · ${run}` : `Списание · ${what}`
}

export function ledgerDescription(item: LedgerItem) {
  const meta = item.metadata_ || (item as { metadata?: Record<string, unknown> }).metadata || {}
  if (String(meta.source || '') === 'admin') {
    const note = String(meta.note || '').trim()
    const base = Number(item.amount) >= 0 ? 'Начисление администратором' : 'Корректировка администратором'
    return note ? `${base} · ${note}` : base
  }
  switch (item.kind) {
    case 'credit':
      return 'Стартовые credits'
    case 'purchase':
      return 'Покупка тарифа'
    case 'refund':
      return shortRunId(item.reference) ? `Возврат · ${shortRunId(item.reference)}` : 'Возврат'
    case 'charge':
      return chargeLabel(item)
    default:
      return item.kind
  }
}

export function visibleLedgerEntries(items: LedgerItem[]) {
  return items
    .filter(item => VISIBLE_LEDGER_KINDS.has(item.kind))
    .filter(item => Number(item.amount) !== 0)
    .map(item => ({
      id: item.id,
      created_at: item.created_at,
      amount: Number(item.amount),
      kind: item.kind,
      description: ledgerDescription(item)
    }))
}
