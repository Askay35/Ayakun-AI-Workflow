const LABELS: Record<string, string> = {
  queued: 'В очереди',
  running: 'Выполняется',
  succeeded: 'Готово',
  failed: 'Ошибка',
  cancelled: 'Отменён',
  pending: 'Ожидает'
}

export function statusKey(status?: string | { value?: string } | null) {
  if (!status) return ''
  if (typeof status === 'string') return status.trim().toLowerCase()
  return String(status.value || '').trim().toLowerCase()
}

export function statusLabel(status?: string | { value?: string } | null) {
  const key = statusKey(status)
  return LABELS[key] || key || '—'
}

export function statusColor(status?: string | { value?: string } | null) {
  const key = statusKey(status)
  if (key === 'succeeded') return 'success'
  if (key === 'failed') return 'error'
  if (key === 'running') return 'info'
  return 'neutral'
}
