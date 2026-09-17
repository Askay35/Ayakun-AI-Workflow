import type { ScheduleSlot } from '~/utils/schedule'

export type Id = string
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type NodeRunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type NodeKind =
  | 'web_search'
  | 'prompt'
  | 'http_request'
  | 'if_else'
  | 'telegram_send'
  | 'webhook'
  | 'google_sheets'
  | 'email'
  | 'data_transform'
  | 'sql_query'
export type SearchPeriod = 'h' | 'd' | 'w' | 'm' | 'y'

export interface ApiEnvelope<T> {
  success: boolean
  data: T
  message?: string
  error?: { code?: string; message?: string }
}

export interface GmailAccount {
  id: number
  email?: string | null
}

export interface User {
  id: number
  chat_id?: number
  email?: string
  name?: string
  avatar_url?: string
  identities?: Array<{ provider: 'email' | 'google' | 'telegram'; label?: string }>
  gmail_accounts?: GmailAccount[]
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: User
  gmail_account?: GmailAccount | null
}

export interface WorkflowNode {
  id: Id
  type: NodeKind
  position: { x: number; y: number }
  parents: Id[]
  children: Id[]
  true_children?: Id[]
  false_children?: Id[]
  data: {
    label: string
    query?: string
    period?: SearchPeriod
    prompt?: string
    instructions?: string
    output_format?: string
    model?: string
    complexity?: 'simple_text' | 'complex_text'
    max_output_tokens?: number
    max_run_credits?: number
    request_json?: string
    condition?: string
    chat_id?: string
    bot_token?: string
    message?: string
    assignments?: Array<{ key: string; value: string }>
    operation?: string
    spreadsheet_id?: string
    sheet_range?: string
    access_token?: string
    service_account_json?: string
    api_key?: string
    values_json?: string
    to?: string
    subject?: string
    body?: string
    fields?: string
    mapping_json?: string
    sort_field?: string
    sort_direction?: 'asc' | 'desc'
    path?: string
    engine?: 'postgresql' | 'mysql' | 'clickhouse'
    dsn?: string
    status?: RunStatus
    output?: string
  }
}

export interface Workflow {
  id: Id
  name: string
  description?: string
  status: 'draft' | 'published' | 'archived'
  updated_at: string
  version?: number
  schedule_cron?: string | null
  schedule_slots?: ScheduleSlot[]
  schedule_timezone?: string
  next_run_at?: string | null
  estimated_run_cost?: number
  variables?: Record<string, string | number | boolean | null>
  webhook_token?: string | null
  solo_run_blocked_node_types?: string[]
  draft_graph: { nodes: WorkflowNode[] }
}

export interface ValidationResult {
  valid: boolean
  errors: string[]
}

export interface NodeRun {
  node_id: Id
  node_type: NodeKind
  label?: string | null
  status: NodeRunStatus
  attempt?: number
  output?: Record<string, any> | any[]
  citations?: Array<{ title: string; url: string; date?: string }>
  error?: string
  started_at?: string | null
  finished_at?: string | null
}

export interface WorkflowRun {
  id: Id
  workflow_id: Id
  workflow_name?: string
  status: RunStatus
  input?: Record<string, any>
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
  cost?: number
  node_runs?: NodeRun[]
}

export interface Plan {
  id: number
  code: string
  name: string
  price: number
  currency: string
  limits: Record<string, number>
}

export interface BillingSummary {
  plan?: Plan
  balance: number
  usage_this_month: number
  ledger: Array<{ id: Id; created_at: string; amount: number; kind?: string; description: string }>
}

export interface PricingRate {
  id: number
  provider: string
  model: string
  input_cache_hit_credits_per_1k: number
  input_cache_miss_credits_per_1k: number
  output_credits_per_1k: number
  search_credits: number
  provider_costs: Record<string, number>
  active: boolean
}

export interface AdminConfig {
  pricing: PricingRate[]
  plans: Plan[]
  settings: Array<{ key: string; value: string | number | boolean; description: string }>
}

export interface AdminPage<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AdminIdentity {
  provider: string
  subject: string
  created_at: string
}

export interface AdminLedgerEntry {
  id: string
  kind: string
  amount: number
  reference?: string | null
  metadata?: Record<string, unknown>
  created_at: string
}

export interface AdminUserRecord {
  id: number
  name: string
  email?: string | null
  chat_id?: number | null
  email_verified: boolean
  is_active: boolean
  balance: number
  reserved: number
  identities: AdminIdentity[]
  ledger?: AdminLedgerEntry[]
  created_at: string
  updated_at: string
}

export interface AdminPaymentRecord {
  id: string
  user_id: number
  user_name?: string | null
  user_email?: string | null
  plan_id?: number | null
  plan_name?: string | null
  plan_code?: string | null
  credits?: number | null
  provider: string
  provider_payment_id?: string | null
  amount: number
  status: string
  created_at: string
  updated_at: string
}

export interface AdminWorkflowRecord {
  id: string
  owner_id: number
  owner_name?: string | null
  owner_email?: string | null
  name: string
  description?: string | null
  status: 'draft' | 'published' | 'archived'
  schedule_cron?: string | null
  schedule_timezone: string
  next_run_at?: string | null
  estimated_run_cost: number
  nodes_count: number
  created_at: string
  updated_at: string
}

export interface AdminRunRecord {
  id: string
  workflow_id: string
  workflow_name?: string | null
  workflow_version_id: string
  owner_id: number
  owner_name?: string | null
  owner_email?: string | null
  status: RunStatus
  error?: string | null
  cost: number
  cancel_requested: boolean
  started_at?: string | null
  finished_at?: string | null
  created_at: string
}

export interface AdminListQuery {
  q?: string
  status?: string
  is_active?: boolean | string
  user_id?: number | string
  page?: number
  page_size?: number
}
