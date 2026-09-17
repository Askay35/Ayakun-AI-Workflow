import type {
  AdminConfig, AdminListQuery, AdminPage, AdminPaymentRecord, AdminRunRecord,
  AdminUserRecord, AdminWorkflowRecord, ApiEnvelope, AuthTokens, BillingSummary, Plan, PricingRate,
  User, ValidationResult, Workflow, WorkflowNode, WorkflowRun
} from '~/types/api'
import { visibleLedgerEntries } from '~/utils/ledger'
import type { ScheduleSlot } from '~/utils/schedule'

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
  const { t } = useI18n()
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

  const assignmentsOf = (node: WorkflowNode) =>
    (node.data.assignments || [])
      .map(item => ({ key: item.key?.trim() || '', value: item.value || '' }))
      .filter(item => /^[A-Za-z_][A-Za-z0-9_]*$/.test(item.key))

  const serializeNode = (node: WorkflowNode) => {
    const base = {
      id: node.id,
      type: node.type,
      parents: node.parents || [],
      children: node.children || [],
      position: node.position,
      label: node.data.label
    }
    if (node.type === 'web_search') {
      return { ...base, query: node.data.query || '', period: node.data.period || null }
    }
    if (node.type === 'prompt') {
      return {
        ...base,
        prompt: node.data.prompt || '',
        instructions: node.data.instructions || '',
        output_format: node.data.output_format || '',
        complexity: node.data.complexity || 'simple_text',
        max_output_tokens: Number(node.data.max_output_tokens) || 8000,
        assignments: assignmentsOf(node)
      }
    }
    if (node.type === 'http_request') {
      return { ...base, request_json: node.data.request_json || '', assignments: assignmentsOf(node) }
    }
    if (node.type === 'if_else') {
      return {
        ...base,
        condition: node.data.condition || '',
        true_children: node.true_children || [],
        false_children: node.false_children || []
      }
    }
    if (node.type === 'telegram_send') {
      return {
        ...base,
        chat_id: node.data.chat_id || '',
        bot_token: node.data.bot_token || '',
        message: node.data.message || ''
      }
    }
    if (node.type === 'webhook') return base
    if (node.type === 'google_sheets') {
      return {
        ...base,
        operation: node.data.operation || 'read',
        spreadsheet_id: node.data.spreadsheet_id || '',
        sheet_range: node.data.sheet_range || 'Sheet1!A1:Z',
        access_token: node.data.access_token || '',
        service_account_json: node.data.service_account_json || '',
        api_key: node.data.api_key || '',
        values_json: node.data.values_json || '',
        assignments: assignmentsOf(node)
      }
    }
    if (node.type === 'email') {
      return {
        ...base,
        to: node.data.to || '',
        subject: node.data.subject || '',
        body: node.data.body || '',
        assignments: assignmentsOf(node)
      }
    }
    if (node.type === 'data_transform') {
      return {
        ...base,
        operation: node.data.operation || 'select',
        fields: node.data.fields || '',
        mapping_json: node.data.mapping_json || '',
        condition: node.data.condition || '',
        sort_field: node.data.sort_field || '',
        sort_direction: node.data.sort_direction || 'asc',
        path: node.data.path || '',
        assignments: assignmentsOf(node)
      }
    }
    return {
      ...base,
      engine: node.data.engine || 'postgresql',
      dsn: node.data.dsn || '',
      query: node.data.query || '',
      assignments: assignmentsOf(node)
    }
  }

  const serializeGraph = (graph: Workflow['draft_graph']) => ({
    nodes: graph.nodes.map(serializeNode)
  })

  const normalizeWorkflow = (workflow: any): Workflow => {
    const graph = workflow.draft_graph || workflow.graph || { nodes: [] }
    const nodes = (graph.nodes || []).map((node: any, index: number) => {
      const kind = node.type === 'gmail' ? 'email' : node.type
      if (node.data) {
        return {
          ...node,
          type: kind,
          parents: [...(node.parents || node.data.parents || [])],
          children: [...(node.children || node.data.children || [])],
          true_children: [...(node.true_children || node.data.true_children || [])],
          false_children: [...(node.false_children || node.data.false_children || [])],
          data: {
            ...node.data,
            body: node.data.body || node.data.message || '',
            max_output_tokens: Number(node.data.max_output_tokens ?? node.max_output_tokens) || 8000,
            assignments: node.data.assignments || node.assignments || []
          }
        }
      }
      return {
        id: node.id,
        type: kind,
        parents: [...(node.parents || [])],
        children: [...(node.children || [])],
        true_children: [...(node.true_children || [])],
        false_children: [...(node.false_children || [])],
        position: node.position || { x: 80 + index * 280, y: 160 },
        data: {
          label: node.label || kind,
          query: node.query,
          period: node.period || undefined,
          prompt: node.prompt,
          instructions: node.instructions,
          output_format: node.output_format,
          model: node.model,
          complexity: node.complexity || (String(node.model || '').includes('pro') ? 'complex_text' : 'simple_text'),
          max_output_tokens: Number(node.max_output_tokens) || 8000,
          request_json: typeof node.request_json === 'string'
            ? node.request_json
            : node.request_json
              ? JSON.stringify(node.request_json, null, 2)
              : undefined,
          condition: node.condition,
          chat_id: node.chat_id != null && node.chat_id !== '' ? String(node.chat_id) : undefined,
          bot_token: node.bot_token || undefined,
          message: node.message || '',
          assignments: node.assignments || [],
          operation: node.operation,
          spreadsheet_id: node.spreadsheet_id,
          sheet_range: node.sheet_range,
          access_token: node.access_token,
          service_account_json: node.service_account_json,
          api_key: node.api_key,
          values_json: typeof node.values_json === 'string'
            ? node.values_json
            : node.values_json
              ? JSON.stringify(node.values_json, null, 2)
              : undefined,
          to: node.to,
          subject: node.subject,
          body: node.body || node.message || '',
          fields: node.fields,
          mapping_json: typeof node.mapping_json === 'string'
            ? node.mapping_json
            : node.mapping_json
              ? JSON.stringify(node.mapping_json, null, 2)
              : undefined,
          sort_field: node.sort_field,
          sort_direction: node.sort_direction,
          path: node.path,
          engine: node.engine,
          dsn: node.dsn
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
      variables: workflow.variables && typeof workflow.variables === 'object' ? workflow.variables : {},
      solo_run_blocked_node_types: Array.isArray(workflow.solo_run_blocked_node_types)
        ? workflow.solo_run_blocked_node_types
        : ['if_else'],
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
      requestEmailRegister: (email: string, password: string, name: string) =>
        request<void>('/auth/register', { method: 'POST', body: { email, password, name } }),
      confirmEmailRegister: (email: string, code: string) =>
        request<AuthTokens>('/auth/register/confirm', { method: 'POST', body: { email, code } }),
      telegram: (code: string) => request<AuthTokens>('/auth/login/telegram', { method: 'POST', body: { code } }),
      telegramLink: (code: string) => request<User>('/auth/telegram/link', { method: 'POST', body: { code } }),
      updateProfile: (body: { name?: string; email?: string }) => request<User>('/auth/profile', { method: 'PATCH', body }),
      confirmEmailLink: (email: string, code: string) => request<User>('/auth/email/link', { method: 'POST', body: { email, code } }),
      googleStart: (redirectUri: string, codeChallenge: string, purpose: 'login' | 'gmail' | 'link' = 'login') => request<{ authorization_url: string; state: string }>('/auth/google/authorize', {
        method: 'POST', body: { redirect_uri: redirectUri, code_challenge: codeChallenge, purpose }
      }),
      googleCallback: (code: string, state: string, codeVerifier: string, redirectUri: string) => request<AuthTokens>('/auth/google/code', {
        method: 'POST', body: { code, state, code_verifier: codeVerifier, redirect_uri: redirectUri }
      }),
      disconnectGmail: (accountId: number) => request<User>(`/auth/google/gmail/${accountId}`, { method: 'DELETE' }),
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
          name?: string
          schedule?: { time: string; weekdays: number[] } | null
          schedule_slots?: ScheduleSlot[]
          schedule_enabled?: boolean
          schedule_cron?: string | null
          schedule_timezone?: string
          variables?: Record<string, string | number | boolean | null>
          rotate_webhook_token?: boolean
        } = {}
      ) => request<Workflow>(`/workflows/${id}`, {
        method: 'PATCH',
        body: { graph: serializeGraph(graph), ...extras }
      }).then(normalizeWorkflow),
      rename: (id: string, name: string) =>
        request<Workflow>(`/workflows/${id}`, { method: 'PATCH', body: { name } }).then(normalizeWorkflow),
      validate: (id: string) => request<ValidationResult>(`/workflows/${id}/validate`, { method: 'POST' }),
      publish: (id: string) => request<Workflow>(`/workflows/${id}/publish`, { method: 'POST' }).then(normalizeWorkflow),
      run: (id: string) => request<WorkflowRun>(`/workflows/${id}/runs`, { method: 'POST', body: { input: {} } }),
      runNode: (id: string, nodeId: string) =>
        request<WorkflowRun>(`/workflows/${id}/nodes/${nodeId}/runs`, { method: 'POST', body: { input: {} } }),
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
      wallet: () => request<{ balance: number }>('/billing/wallet'),
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
          })), t)
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
      }),
      listUsers: (credentials: string, query: AdminListQuery = {}) =>
        adminRequest<AdminPage<AdminUserRecord>>('/admin/users', credentials, { query }),
      getUser: (credentials: string, id: number) =>
        adminRequest<AdminUserRecord>(`/admin/users/${id}`, credentials),
      updateUser: (credentials: string, id: number, body: Record<string, unknown>) =>
        adminRequest<AdminUserRecord>(`/admin/users/${id}`, credentials, {
          method: 'PATCH',
          body: { ...body, request_id: crypto.randomUUID() }
        }),
      loginAsUser: (credentials: string, id: number) =>
        adminRequest<AuthTokens>(`/admin/users/${id}/session`, credentials, { method: 'POST' }),
      deleteUser: (credentials: string, id: number) =>
        adminRequest<{ ok: boolean }>(`/admin/users/${id}`, credentials, {
          method: 'DELETE',
          query: { request_id: crypto.randomUUID() }
        }),
      listPayments: (credentials: string, query: AdminListQuery = {}) =>
        adminRequest<AdminPage<AdminPaymentRecord>>('/admin/payments', credentials, { query }),
      updatePayment: (credentials: string, id: string, body: Record<string, unknown>) =>
        adminRequest<AdminPaymentRecord>(`/admin/payments/${id}`, credentials, {
          method: 'PATCH',
          body: { ...body, request_id: crypto.randomUUID() }
        }),
      deletePayment: (credentials: string, id: string) =>
        adminRequest<{ ok: boolean }>(`/admin/payments/${id}`, credentials, {
          method: 'DELETE',
          query: { request_id: crypto.randomUUID() }
        }),
      listWorkflows: (credentials: string, query: AdminListQuery = {}) =>
        adminRequest<AdminPage<AdminWorkflowRecord>>('/admin/workflows', credentials, { query }),
      updateWorkflow: (credentials: string, id: string, body: Record<string, unknown>) =>
        adminRequest<AdminWorkflowRecord>(`/admin/workflows/${id}`, credentials, {
          method: 'PATCH',
          body: { ...body, request_id: crypto.randomUUID() }
        }),
      deleteWorkflow: (credentials: string, id: string) =>
        adminRequest<{ ok: boolean }>(`/admin/workflows/${id}`, credentials, {
          method: 'DELETE',
          query: { request_id: crypto.randomUUID() }
        }),
      listRuns: (credentials: string, query: AdminListQuery = {}) =>
        adminRequest<AdminPage<AdminRunRecord>>('/admin/runs', credentials, { query }),
      updateRun: (credentials: string, id: string, body: Record<string, unknown>) =>
        adminRequest<AdminRunRecord>(`/admin/runs/${id}`, credentials, {
          method: 'PATCH',
          body: { ...body, request_id: crypto.randomUUID() }
        }),
      deleteRun: (credentials: string, id: string) =>
        adminRequest<{ ok: boolean }>(`/admin/runs/${id}`, credentials, {
          method: 'DELETE',
          query: { request_id: crypto.randomUUID() }
        })
    }
  }
}
