export type Id = string
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type NodeRunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type NodeKind = 'web_search' | 'prompt' | 'telegram_send'

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
  data: {
    label: string
    query?: string
    prompt?: string
    model?: string
    complexity?: 'simple_text' | 'complex_text'
    chat_id?: string
    status?: RunStatus
    output?: string
  }
}

export interface WorkflowEdge {
  id: Id
  source: Id
  target: Id
}

export interface Workflow {
  id: Id
  name: string
  description?: string
  status: 'draft' | 'published' | 'archived'
  updated_at: string
  version?: number
  schedule_cron?: string | null
  schedule_timezone?: string
  next_run_at?: string | null
  estimated_run_cost?: number
  draft_graph: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }
}

export interface ValidationResult {
  valid: boolean
  errors: string[]
}

export interface NodeRun {
  id: Id
  node_id: Id
  status: NodeRunStatus
  output?: Record<string, any>
  citations?: Array<{ title: string; url: string }>
  cost?: number
  error?: string
}

export interface WorkflowRun {
  id: Id
  workflow_id: Id
  workflow_name?: string
  status: RunStatus
  created_at: string
  finished_at?: string
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
  ledger: Array<{ id: Id; created_at: string; amount: number; description: string }>
}
