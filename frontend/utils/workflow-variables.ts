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
    chunks.push(node.data.chat_id, node.data.message)
  } else if (node.type === 'google_sheets') {
    chunks.push(node.data.spreadsheet_id, node.data.sheet_range, node.data.values_json)
  } else if (node.type === 'email') {
    chunks.push(node.data.to, node.data.subject, node.data.body)
  } else if (node.type === 'sql_query') {
    chunks.push(node.data.dsn, node.data.query)
  } else if (node.type === 'loop') {
    chunks.push(node.data.source, node.data.times, node.data.while_value)
    if (node.data.while_variable) chunks.push(`{{${node.data.while_variable}}}`)
  } else if (node.type === 'delay') {
    chunks.push(node.data.amount)
  } else if (node.type === 'yandex_disk') {
    chunks.push(node.data.remote_path, node.data.local_path, node.data.content)
  } else if (node.type === 'image_generation' || node.type === 'image_recognition') {
    chunks.push(node.data.prompt)
  } else if (node.type === 'image' || node.type === 'audio_transcription') {
    chunks.push(node.data.url, node.data.prompt)
  } else if (node.type === 'slack') {
    chunks.push(node.data.webhook_url, node.data.channel, node.data.message)
  } else if (node.type === 'trello') {
    chunks.push(node.data.list_id, node.data.card_id, node.data.name, node.data.description)
  } else if (node.type === 'jira') {
    chunks.push(node.data.base_url, node.data.project_key, node.data.summary, node.data.description, node.data.jql, node.data.issue_key, node.data.comment)
  } else if (node.type === 'excel') {
    chunks.push(node.data.file_path, node.data.worksheet, node.data.cell_range, node.data.table, node.data.values_json)
  } else if (node.type === 'spreadsheet') {
    chunks.push(node.data.path, node.data.filename)
  } else if (node.type === 'linkedin') {
    chunks.push(node.data.author, node.data.text)
  } else if (node.type === 'bitrix24') {
    chunks.push(node.data.webhook_url, node.data.item_id, node.data.fields_json, node.data.filter_json)
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
