import type {
  AdminConfig, ApiEnvelope, AuthTokens, BillingSummary, Plan, PricingRate,
  User, ValidationResult, Workflow, WorkflowNode, WorkflowRun
} from '~/types/api'
import { visibleLedgerEntries } from '~/utils/ledger'

let refreshRequest: Promise<string | null> | null = null

export const apiErrorMessage = (error: unknown, fallback = 'Что-то пошло не так') => {
  const data = (error as any)?.data
  const message = data?.error?.message ?? data?.message ?? data?.detail
  if (typeof message === 'string' && message.trim()) return message
  if (Array.isArray(message)) {
    return message.map((item) => (typeof item === 'string' ? item : item?.msg || JSON.stringify(item))).join(', ')
  }
  const status = (error as any)?.statusCode || (error as any)?.status
  if (status) return `Ошибка ${status}`
  return (error as any)?.message || fallback
}

export const useApi = () => {
  const config = useRuntimeConfig()
  const apiBase = computed(() => {
    if (import.meta.server && config.apiBase) return String(config.apiBase)
    return String(config.public.apiBase)
  })
  const accessToken = useState<string | null>('ayakun_access', () => null)
  const refreshToken = useState<string | null>('ayakun_refresh', () => null)

  const unwrap = <T>(value: T | ApiEnvelope<T>): T =>
    typeof value === 'object' && value !== null && 'success' in value
      ? (value as ApiEnvelope<T>).data
      : value as T

  const refresh = async () => {
    if (!refreshToken.value) return null
    refreshRequest ??= $fetch<AuthTokens | ApiEnvelope<AuthTokens>>('/auth/refresh', {
      baseURL: apiBase.value,
      method: 'POST',
      body: { refresh_token: refreshToken.value }
    }).then((response) => {
      const tokens = unwrap(response)
      accessToken.value = tokens.access_token
      refreshToken.value = tokens.refresh_token
      return tokens.access_token
    }).catch((error: any) => {
      const status = error?.statusCode || error?.status
      if (status === 401 || status === 403) {
        accessToken.value = null
        refreshToken.value = null
      }
      return null
    }).finally(() => { refreshRequest = null })
    return refreshRequest
  }

  const request = async <T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}) => {
    try {
      return unwrap(await $fetch<T | ApiEnvelope<T>>(path, {
        ...options,
        baseURL: apiBase.value,
        headers: { ...options.headers, ...(accessToken.value ? { Authorization: `Bearer ${accessToken.value}` } : {}) }
      }))
    } catch (error: any) {
      if ((error?.statusCode === 401 || error?.status === 401) && refreshToken.value) {
        const token = await refresh()
        if (token) {
          return unwrap(await $fetch<T | ApiEnvelope<T>>(path, {
            ...options,
            baseURL: apiBase.value,
            headers: { ...options.headers, Authorization: `Bearer ${token}` }
          }))
        }
      }
      throw error
    }
  }

  const adminRequest = async <T>(
    path: string,
    credentials: string,
    options: Parameters<typeof $fetch<T>>[1] = {}
  ) => unwrap(await $fetch<T | ApiEnvelope<T>>(path, {
    ...options,
    baseURL: apiBase.value,
    headers: { ...options.headers, Authorization: `Basic ${credentials}` }
  }))

  const serializeGraph = (graph: Workflow['draft_graph']) => ({
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      parents: node.parents || [],
      children: node.children || [],
      position: node.position,
      label: node.data.label,
      ...(node.type === 'web_search'
        ? {
            query: node.data.query || '',
            period: node.data.period || null
          }
        : node.type === 'prompt'
          ? {
              prompt: node.data.prompt || '',
              instructions: node.data.instructions || '',
              output_format: node.data.output_format || '',
              complexity: node.data.complexity || 'simple_text'
            }
          : node.type === 'http_request'
            ? {
                request_json: node.data.request_json || ''
              }
            : node.type === 'if_else'
              ? {
                  condition: node.data.condition || '',
                  true_children: node.true_children || [],
                  false_children: node.false_children || []
                }
              : {
                  chat_id: node.data.chat_id ? Number(node.data.chat_id) : undefined,
                  message: node.data.message || ''
                })
    }))
  })

  const normalizeWorkflow = (workflow: any): Workflow => {
    const graph = workflow.draft_graph || workflow.graph || { nodes: [] }
    const nodes = (graph.nodes || []).map((node: any, index: number) => {
      if (node.data) {
        return {
          ...node,
          parents: [...(node.parents || node.data.parents || [])],
          children: [...(node.children || node.data.children || [])],
          true_children: [...(node.true_children || node.data.true_children || [])],
          false_children: [...(node.false_children || node.data.false_children || [])]
        }
      }
      return {
        id: node.id,
        type: node.type,
        parents: [...(node.parents || [])],
        children: [...(node.children || [])],
        true_children: [...(node.true_children || [])],
        false_children: [...(node.false_children || [])],
        position: node.position || { x: 80 + index * 280, y: 160 },
        data: {
          label: node.label || node.type,
          query: node.query,
          period: node.period || undefined,
          prompt: node.prompt,
          instructions: node.instructions,
          output_format: node.output_format,
          model: node.model,
          complexity: node.complexity || (String(node.model || '').includes('pro') ? 'complex_text' : 'simple_text'),
          request_json: typeof node.request_json === 'string'
            ? node.request_json
            : node.request_json
              ? JSON.stringify(node.request_json, null, 2)
              : undefined,
          condition: node.condition,
          chat_id: node.chat_id ? String(node.chat_id) : undefined,
          message: node.message || ''
        }
      }
    })
    for (const edge of graph.edges || []) {
      const source = nodes.find((node: WorkflowNode) => node.id === edge.source)
      const target = nodes.find((node: WorkflowNode) => node.id === edge.target)
      if (source && edge.target && !source.children.includes(edge.target)) source.children.push(edge.target)
      if (target && edge.source && !target.parents.includes(edge.source)) target.parents.push(edge.source)
    }
    return {
      ...workflow,
      estimated_run_cost: Number(workflow.estimated_run_cost || 0),
      draft_graph: { nodes }
    }
  }

  return {
    accessToken,
    refreshToken,
    request,
    auth: {
      me: () => request<User>('/auth/me'),
      email: (email: string, password: string, mode: 'login' | 'register', name?: string) =>
        request<AuthTokens>(mode === 'login' ? '/auth/login' : '/auth/register', {
          method: 'POST',
          body: mode === 'login' ? { email, password } : { email, password, name }
        }),
      telegram: (code: string) => request<AuthTokens>('/auth/login/telegram', { method: 'POST', body: { code } }),
      googleStart: (redirectUri: string, codeChallenge: string) => request<{ authorization_url: string; state: string }>('/auth/google/authorize', {
        method: 'POST', body: { redirect_uri: redirectUri, code_challenge: codeChallenge }
      }),
      googleCallback: (code: string, state: string, codeVerifier: string, redirectUri: string) => request<AuthTokens>('/auth/google/code', {
        method: 'POST', body: { code, state, code_verifier: codeVerifier, redirect_uri: redirectUri }
      }),
      forgot: (email: string) => request<void>('/auth/password-reset/request', { method: 'POST', body: { email } }),
      logout: () => request<void>('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken.value } })
    },
    workflows: {
      list: async () => (await request<Workflow[]>('/workflows')).map(normalizeWorkflow),
      get: async (id: string) => normalizeWorkflow(await request<Workflow>(`/workflows/${id}`)),
      create: async (body: Pick<Workflow, 'name' | 'description'>) =>
        normalizeWorkflow(await request<Workflow>('/workflows', { method: 'POST', body })),
      save: (
        id: string,
        graph: Workflow['draft_graph'],
        extras: {
          schedule?: { time: string; weekdays: number[] } | null
          schedule_cron?: string | null
          schedule_timezone?: string
        } = {}
      ) => request<Workflow>(`/workflows/${id}`, {
        method: 'PATCH',
        body: { graph: serializeGraph(graph), ...extras }
      }).then(normalizeWorkflow),
      validate: (id: string) => request<ValidationResult>(`/workflows/${id}/validate`, { method: 'POST' }),
      publish: (id: string) => request<Workflow>(`/workflows/${id}/publish`, { method: 'POST' }).then(normalizeWorkflow),
      run: (id: string) => request<WorkflowRun>(`/workflows/${id}/runs`, { method: 'POST', body: { input: {} } }),
      delete: (id: string) => request<void>(`/workflows/${id}`, { method: 'DELETE' })
    },
    runs: {
      list: () => request<WorkflowRun[]>('/workflows/runs'),
      get: async (id: string): Promise<WorkflowRun> => {
        const [run, nodes] = await Promise.all([
          request<WorkflowRun>(`/workflows/runs/${id}`),
          request<WorkflowRun['node_runs']>(`/workflows/runs/${id}/nodes`)
        ])
        return {
          ...run,
          node_runs: (nodes || []).map(node => ({
            ...node,
            // web_search отдаёт список результатов, остальные узлы — объект с citations.
            citations: Array.isArray(node.output)
              ? node.output
                  .filter((item: any) => item?.url)
                  .map((item: any) => ({ title: item.title || item.url, url: item.url, date: item.date }))
              : (node.output as any)?.citations
          }))
        } as WorkflowRun
      },
      cancel: (id: string) => request<WorkflowRun>(`/workflows/runs/${id}/cancel`, { method: 'POST' })
    },
    billing: {
      plans: () => request<Plan[]>('/billing/plans'),
      summary: async (): Promise<BillingSummary> => {
        const [wallet, ledger, usage] = await Promise.all([
          request<{ balance: number }>('/billing/wallet'),
          request<Array<{
            id: string
            created_at: string
            amount: number
            kind: string
            reference?: string
            metadata?: Record<string, unknown>
            metadata_?: Record<string, unknown>
          }>>('/billing/ledger'),
          request<Array<{ cost: number }>>('/billing/usage')
        ])
        return {
          balance: Number(wallet.balance),
          usage_this_month: usage.reduce((sum, item) => sum + Number(item.cost), 0),
          ledger: visibleLedgerEntries(ledger.map(item => ({
            ...item,
            metadata_: item.metadata_ || item.metadata
          })))
        }
      },
      checkout: (planId: number, idempotencyKey: string, customerEmail?: string) => request<{ confirmation_url: string | null }>('/billing/checkout', {
        method: 'POST',
        body: {
          plan_id: planId,
          idempotency_key: idempotencyKey,
          ...(customerEmail ? { customer_email: customerEmail } : {})
        }
      })
    },
    admin: {
      config: (credentials: string) => adminRequest<AdminConfig>('/admin/config', credentials),
      updatePricing: (credentials: string, rate: PricingRate) =>
        adminRequest<PricingRate>(`/admin/pricing/${rate.id}`, credentials, {
          method: 'PUT',
          body: {
            search_credits: Number(rate.search_credits),
            active: rate.active,
            request_id: crypto.randomUUID()
          }
        }),
      updatePlan: (credentials: string, plan: Plan) =>
        adminRequest<Plan>(`/admin/plans/${plan.id}`, credentials, {
          method: 'PUT',
          body: {
            name: plan.name,
            price: Number(plan.price),
            currency: plan.currency,
            included_credits: Number(plan.limits.included_credits || 0),
            run_cap_credits: Number(plan.limits.run_cap_credits || 0),
            request_id: crypto.randomUUID()
          }
        }),
      updateSetting: (
        credentials: string,
        setting: { key: string; value: string | number | boolean; description: string }
      ) => adminRequest<typeof setting>(`/admin/settings/${setting.key}`, credentials, {
        method: 'PUT',
        body: { value: setting.value, request_id: crypto.randomUUID() }
      })
    }
  }
}
