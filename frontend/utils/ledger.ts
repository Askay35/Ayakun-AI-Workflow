/** Операции, которые меняют баланс с точки зрения пользователя. */
const VISIBLE_LEDGER_KINDS = new Set(['credit', 'purchase', 'charge', 'refund', 'expire', 'referral'])

type LedgerItem = {
  id: string
  created_at: string
  amount: number
  kind: string
  reference?: string | null
  metadata_?: Record<string, unknown> | null
}

type Translate = (path: string, vars?: Record<string, string | number>) => string

function shortRunId(reference?: string | null) {
  if (!reference) return ''
  const id = reference.replace(/^run:/, '')
  return id.length > 8 ? id.slice(0, 8) : id
}

function chargeLabel(item: LedgerItem, t?: Translate) {
  const meta = item.metadata_ || (item as { metadata?: Record<string, unknown> }).metadata || {}
  const provider = String(meta.provider || '')
  // const model = String(meta.model || '')
  const run = shortRunId(item.reference)
  const what =
    provider === 'serper' ? (t ? t('ledger.search') : 'поиск')
      : provider === 'deepseek' || provider === 'qwen' ? `AI обработка`
        : provider === 'telegram' ? 'Telegram'
          : (t ? t('ledger.run') : 'запуск')
  if (t) {
    return run ? t('ledger.chargeRun', { what, run }) : t('ledger.charge', { what })
  }
  return run ? `Списание · ${what} · ${run}` : `Списание · ${what}`
}

export function ledgerDescription(item: LedgerItem, t?: Translate) {
  const meta = item.metadata_ || (item as { metadata?: Record<string, unknown> }).metadata || {}
  if (String(meta.source || '') === 'admin') {
    const note = String(meta.note || '').trim()
    const base = Number(item.amount) >= 0
      ? (t ? t('ledger.adminCredit') : 'Начисление администратором')
      : (t ? t('ledger.adminAdjust') : 'Корректировка администратором')
    return note ? `${base} · ${note}` : base
  }
  switch (item.kind) {
    case 'credit':
      return t ? t('ledger.starter') : 'Стартовые credits'
    case 'purchase': {
      const plan = String(meta.plan_name || '')
      const kind = String(meta.subscription || '')
      if (t && plan && ['new', 'renewal', 'upgrade'].includes(kind)) return t(`ledger.plan_${kind}`, { plan })
      return t ? t('ledger.purchase') : 'Покупка credits'
    }
    case 'referral':
      if (String(meta.role || '') === 'referee') return t ? t('ledger.referralReferee') : 'Бонус за регистрацию по приглашению'
      return t ? t('ledger.referralReferrer', { name: String(meta.referee_name || '—') }) : 'Бонус за приглашённого'
    case 'expire':
      return t ? t('ledger.expire') : 'Сгорание неиспользованных токенов'
    case 'refund':
      if (shortRunId(item.reference)) {
        return t ? t('ledger.refundRun', { run: shortRunId(item.reference) }) : `Возврат · ${shortRunId(item.reference)}`
      }
      return t ? t('ledger.refund') : 'Возврат'
    case 'charge':
      return chargeLabel(item, t)
    default:
      return item.kind
  }
}

export function visibleLedgerEntries(items: LedgerItem[], t?: Translate) {
  return items
    .filter(item => VISIBLE_LEDGER_KINDS.has(item.kind))
    .filter(item => Number(item.amount) !== 0)
    .map(item => ({
      id: item.id,
      created_at: item.created_at,
      amount: Number(item.amount),
      kind: item.kind,
      description: ledgerDescription(item, t)
    }))
}
