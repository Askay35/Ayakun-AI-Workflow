import type { WorkflowNode } from '~/types/api'

export const VARIABLE_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/
const VARIABLE_TOKEN_RE = /\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}/g

export type VariableMark = 'write' | 'read' | 'undefined'
export type VariableHint = { name: string; mark: VariableMark }
export type VariableRow = { key: string; value: string }

export function extractVariableNames(text: string | undefined | null): string[] {
  if (!text) return []
  const names: string[] = []
  const seen = new Set<string>()
  for (const match of text.matchAll(VARIABLE_TOKEN_RE)) {
    const name = match[1]
    if (!name || seen.has(name)) continue
    seen.add(name)
    names.push(name)
  }
  return names
}

export function nodeAssignmentKeys(node: WorkflowNode): string[] {
  const keys: string[] = []
  const seen = new Set<string>()
  for (const item of node.data.assignments || []) {
    const key = (item.key || '').trim()
    if (!key || seen.has(key)) continue
    seen.add(key)
    keys.push(key)
  }
  return keys
}

export function nodeUsedKeys(node: WorkflowNode): string[] {
  const chunks: Array<string | undefined> = []
  if (node.type === 'prompt') {
    chunks.push(node.data.prompt, node.data.instructions, node.data.output_format)
  } else if (node.type === 'http_request') {
    chunks.push(node.data.request_json)
  } else if (node.type === 'if_else' || node.type === 'data_transform') {
    chunks.push(node.data.condition, node.data.mapping_json, node.data.fields, node.data.sort_field, node.data.path)
  } else if (node.type === 'telegram_send') {
    chunks.push(node.data.message)
  } else if (node.type === 'google_sheets') {
    chunks.push(node.data.spreadsheet_id, node.data.sheet_range, node.data.values_json)
  } else if (node.type === 'email') {
    chunks.push(node.data.to, node.data.subject, node.data.body)
  } else if (node.type === 'sql_query') {
    chunks.push(node.data.dsn, node.data.query)
  }
  for (const item of node.data.assignments || []) chunks.push(item.value)
  const names: string[] = []
  const seen = new Set<string>()
  for (const chunk of chunks) {
    for (const name of extractVariableNames(chunk)) {
      if (seen.has(name)) continue
      seen.add(name)
      names.push(name)
    }
  }
  return names
}

export function definedVariableNames(rows: VariableRow[], nodes: WorkflowNode[]): Set<string> {
  const names = new Set<string>()
  for (const row of rows) {
    const key = row.key.trim()
    if (key) names.add(key)
  }
  for (const node of nodes) {
    for (const key of nodeAssignmentKeys(node)) names.add(key)
  }
  return names
}

export function nodeVariableHints(node: WorkflowNode, defined: Set<string>): VariableHint[] {
  const written = new Set(nodeAssignmentKeys(node))
  const used = nodeUsedKeys(node)
  const names: string[] = []
  const seen = new Set<string>()
  for (const name of [...written, ...used]) {
    if (seen.has(name)) continue
    seen.add(name)
    names.push(name)
  }
  return names.map((name) => {
    if (written.has(name)) return { name, mark: 'write' }
    if (!defined.has(name)) return { name, mark: 'undefined' }
    return { name, mark: 'read' }
  })
}

export function variablesFromRecord(record: Record<string, unknown> | undefined | null): VariableRow[] {
  return Object.entries(record || {}).map(([key, value]) => ({
    key,
    value: value == null ? '' : String(value)
  }))
}

export function recordFromVariables(rows: VariableRow[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const row of rows) {
    const key = row.key.trim()
    if (!key || !VARIABLE_NAME_RE.test(key)) continue
    result[key] = row.value
  }
  return result
}

export function cleanAssignments(items: Array<{ key?: string; value?: string }> | undefined) {
  return (items || [])
    .map(item => ({ key: (item.key || '').trim(), value: item.value || '' }))
    .filter(item => VARIABLE_NAME_RE.test(item.key))
}
