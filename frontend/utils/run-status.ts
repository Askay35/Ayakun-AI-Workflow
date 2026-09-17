const LABELS: Record<string, string> = {
  queued: 'status.queued',
  running: 'status.running',
  succeeded: 'status.succeeded',
  failed: 'status.failed',
  cancelled: 'status.cancelled',
  pending: 'status.pending'
}

export function statusKey(status?: string | { value?: string } | null) {
  if (!status) return ''
  if (typeof status === 'string') return status.trim().toLowerCase()
  return String(status.value || '').trim().toLowerCase()
}

export function statusLabel(status?: string | { value?: string } | null, t?: (key: string) => string) {
  const key = statusKey(status)
  const path = LABELS[key]
  if (path && t) return t(path)
  if (path) return path
  return key || '—'
}

export function statusColor(status?: string | { value?: string } | null) {
  const key = statusKey(status)
  if (key === 'succeeded') return 'success'
  if (key === 'failed') return 'error'
  if (key === 'running') return 'info'
  return 'neutral'
}
