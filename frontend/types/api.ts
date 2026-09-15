import type { ScheduleSlot } from '~/utils/schedule'

export type Id = string
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type NodeRunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type NodeKind = 'web_search' | 'prompt' | 'http_request' | 'if_else' | 'telegram_send'
export type SearchPeriod = 'h' | 'd' | 'w' | 'm' | 'y'

export interface ApiEnvelope<T> {
  success: boolean
  data: T
  message?: string
  error?: { code?: string; message?: string }
}

export interface User {
  id: number
  chat_id?: number
  email?: string
  name?: string
  avatar_url?: string
  identities?: Array<{ provider: 'email' | 'google' | 'telegram'; label?: string }>
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: User
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
    message?: string
    assignments?: Array<{ key: string; value: string }>
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
