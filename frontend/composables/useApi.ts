import type {
  ApiEnvelope, AuthTokens, BillingSummary, Plan, User, ValidationResult, Workflow, WorkflowRun
} from '~/types/api'

let refreshRequest: Promise<string | null> | null = null

export const useApi = () => {
  const config = useRuntimeConfig()
  const apiBase = computed(() => {
    if (import.meta.server && config.apiBase) return String(config.apiBase)
    return String(config.public.apiBase)
  })
  const cookieOpts = { path: '/', sameSite: 'lax' as const, maxAge: 60 * 60 * 24 * 30, watch: true as const }
  const accessToken = useCookie<string | null>('yakun_access', cookieOpts)
  const refreshToken = useCookie<string | null>('yakun_refresh', cookieOpts)

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

  const serializeGraph = (graph: Workflow['draft_graph']) => ({
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      label: node.data.label,
      ...(node.type === 'web_search'
        ? { query: node.data.query || '' }
        : node.type === 'prompt'
          ? {
              prompt: node.data.prompt || '',
              complexity: node.data.complexity || 'simple_text'
            }
          : {
              chat_id: node.data.chat_id ? Number(node.data.chat_id) : undefined
            })
    })),
    edges: graph.edges.map(({ source, target }) => ({ source, target }))
  })

  const normalizeWorkflow = (workflow: any): Workflow => {
    const graph = workflow.draft_graph || workflow.graph || { nodes: [], edges: [] }
    return {
      ...workflow,
      estimated_run_cost: Number(workflow.estimated_run_cost || 0),
      draft_graph: {
        nodes: graph.nodes.map((node: any, index: number) => node.data ? node : ({
          id: node.id,
          type: node.type,
          position: node.position || { x: 80 + index * 260, y: 120 },
          data: {
            label: node.label || node.type,
            query: node.query,
            prompt: node.prompt,
            model: node.model,
            complexity: node.complexity || (String(node.model || '').includes('pro') ? 'complex_text' : 'simple_text'),
            chat_id: node.chat_id ? String(node.chat_id) : undefined
          }
        })),
        edges: graph.edges.map((edge: any) => ({
          ...edge,
          id: edge.id || `${edge.source}-${edge.target}`
        }))
      }
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
        extras: { schedule_cron?: string | null; schedule_timezone?: string } = {}
      ) => request<Workflow>(`/workflows/${id}`, {
        method: 'PATCH',
        body: { graph: serializeGraph(graph), ...extras }
      }).then(normalizeWorkflow),
      validate: (id: string) => request<ValidationResult>(`/workflows/${id}/validate`, { method: 'POST' }),
      publish: (id: string) => request<Workflow>(`/workflows/${id}/publish`, { method: 'POST' }).then(normalizeWorkflow).catch((error: any) => { throw new Error(error.message) }),
      run: (id: string) => request<WorkflowRun>(`/workflows/${id}/runs`, { method: 'POST', body: { input: {} } })
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
            citations: node.output?.citations
          }))
        } as WorkflowRun
      },
      cancel: (id: string) => request<WorkflowRun>(`/workflows/runs/${id}/cancel`, { method: 'POST' })
    },
    billing: {
      plans: () => request<Plan[]>('/billing/plans'),
      summary: async (): Promise<BillingSummary> => {
        const [plans, wallet, subscription, ledger, usage] = await Promise.all([
          request<Plan[]>('/billing/plans'),
          request<{ balance: number }>('/billing/wallet'),
          request<{ plan_id: number } | null>('/billing/subscription'),
          request<Array<{ id: string; created_at: string; amount: number; kind: string; reference?: string }>>('/billing/ledger'),
          request<Array<{ cost: number }>>('/billing/usage')
        ])
        return {
          plan: plans.find(plan => plan.id === subscription?.plan_id),
          balance: Number(wallet.balance),
          usage_this_month: usage.reduce((sum, item) => sum + Number(item.cost), 0),
          ledger: ledger.map(item => ({
            id: item.id,
            created_at: item.created_at,
            amount: Number(item.amount),
            description: item.reference || item.kind
          }))
        }
      },
      checkout: (planId: number) => request<{ confirmation_url: string | null }>('/billing/subscription/checkout', {
        method: 'POST', body: { plan_id: planId, idempotency_key: crypto.randomUUID() }
      })
    }
  }
}
