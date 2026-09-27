import type { NodeKind, WorkflowNode } from '~/types/api'

export const NODE_META: Record<NodeKind, { label: string; caption: string; icon: string; accent: string }> = {
  web_search: { label: 'Поиск в сети', caption: 'Поиск в сети', icon: 'i-lucide-search', accent: '#2bbf8e' },
  prompt: { label: 'Обработка', caption: 'AI Prompt', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  http_request: { label: 'HTTP Request', caption: 'HTTP-запрос', icon: 'i-lucide-globe', accent: '#f59e0b' },
  if_else: { label: 'IF ELSE', caption: 'Условие', icon: 'i-lucide-git-branch', accent: '#e8b84a' },
  telegram_send: { label: 'Telegram', caption: 'Отправить сообщение', icon: 'i-lucide-send', accent: '#2aa8e0' },
  webhook: { label: 'Вебхук', caption: 'Запуск по событию', icon: 'i-lucide-webhook', accent: '#f472b6' },
  google_sheets: { label: 'Google Таблицы', caption: 'Строки таблицы', icon: 'i-lucide-table', accent: '#22c55e' },
  email: { label: 'Email', caption: 'Отправить письмо', icon: 'i-lucide-mail', accent: '#ea4335' },
  data_transform: { label: 'Преобразование', caption: 'Данные', icon: 'i-lucide-replace', accent: '#38bdf8' },
  sql_query: { label: 'База данных', caption: 'SQL-запрос', icon: 'i-lucide-database', accent: '#6366f1' },
  loop: { label: 'Цикл', caption: 'Повтор', icon: 'i-lucide-repeat', accent: '#f97316' },
  delay: { label: 'Задержка', caption: 'Пауза', icon: 'i-lucide-timer', accent: '#94a3b8' },
  yandex_disk: { label: 'Яндекс Диск', caption: 'Файлы', icon: 'i-lucide-hard-drive', accent: '#ffcc00' },
  image_generation: { label: 'Генерация изображения', caption: 'Картинка по тексту', icon: 'i-lucide-image-plus', accent: '#ec4899' },
  image: { label: 'Изображение', caption: 'Файл или ссылка', icon: 'i-lucide-image', accent: '#fb7185' },
  image_recognition: { label: 'Распознавание изображения', caption: 'Текст по картинке', icon: 'i-lucide-scan-eye', accent: '#a78bfa' },
  audio_transcription: { label: 'Расшифровка аудио', caption: 'Текст по записи', icon: 'i-lucide-audio-lines', accent: '#14b8a6' },
  slack: { label: 'Slack', caption: 'Сообщение в канал', icon: 'i-simple-icons-slack', accent: '#611f69' },
  trello: { label: 'Trello', caption: 'Карточки на доске', icon: 'i-simple-icons-trello', accent: '#0079bf' },
  jira: { label: 'Jira', caption: 'Задачи проекта', icon: 'i-simple-icons-jira', accent: '#0052cc' },
  excel: { label: 'Excel', caption: 'Книга в OneDrive', icon: 'i-simple-icons-microsoftexcel', accent: '#107c41' },
  file: { label: 'Файл', caption: 'Загрузка с компьютера', icon: 'i-lucide-file-up', accent: '#64748b' },
  spreadsheet: { label: 'Таблица', caption: 'CSV и XLSX', icon: 'i-lucide-table-2', accent: '#0f9d58' },
  linkedin: { label: 'LinkedIn', caption: 'Публикация поста', icon: 'i-simple-icons-linkedin', accent: '#0a66c2' },
  bitrix24: { label: 'Битрикс24', caption: 'CRM: лиды, сделки, контакты', icon: 'i-lucide-building-2', accent: '#0067ff' }
}

export type NodeGroup = 'triggers' | 'ai' | 'logic' | 'data' | 'files' | 'send'

/** В мобильной цепочке шаги идут списком — ветвления и циклы доступны только на холсте. */
export const MOBILE_BLOCKED_TYPES: NodeKind[] = ['if_else', 'loop']

export const NODE_GROUPS: Array<{ key: NodeGroup; types: NodeKind[] }> = [
  { key: 'triggers', types: ['webhook'] },
  { key: 'ai', types: ['prompt', 'web_search', 'image_generation', 'image_recognition', 'audio_transcription'] },
  { key: 'logic', types: ['if_else', 'loop', 'delay', 'data_transform'] },
  { key: 'data', types: ['http_request', 'sql_query', 'google_sheets', 'excel'] },
  { key: 'files', types: ['file', 'spreadsheet', 'image', 'yandex_disk'] },
  { key: 'send', types: ['telegram_send', 'email', 'slack', 'linkedin', 'trello', 'jira', 'bitrix24'] }
]

export const SINGLE_INCOMING_TYPES: NodeKind[] = [
  'telegram_send',
  'http_request',
  'if_else',
  'google_sheets',
  'email',
  'data_transform',
  'sql_query',
  'loop',
  'delay',
  'yandex_disk',
  'image_generation',
  'image',
  'image_recognition',
  'audio_transcription',
  'slack',
  'trello',
  'jira',
  'excel',
  'file',
  'spreadsheet',
  'linkedin',
  'bitrix24'
]

export const DEFAULT_HTTP_REQUEST_JSON = `{
  "method": "GET",
  "url": "https://api.example.com/users/{{$userId}}"
}`

const ASSIGNABLE_TYPES = new Set<NodeKind>(['prompt', 'http_request', 'google_sheets', 'email', 'data_transform', 'sql_query', 'trello', 'jira', 'excel', 'spreadsheet', 'bitrix24'])
const NEW_NODE_DEFAULTS: Partial<Record<NodeKind, Partial<WorkflowNode['data']>>> = {
  slack: { webhook_url: '', bot_token: '', channel: '', message: '' },
  trello: { operation: 'create_card', api_key: '', token: '', list_id: '', card_id: '', name: '', description: '' },
  jira: { operation: 'create_issue', base_url: '', email: '', api_token: '', project_key: '', issue_type: 'Task', summary: '', description: '', jql: '', issue_key: '', comment: '' },
  excel: { operation: 'read', access_token: '', file_path: '', worksheet: 'Sheet1', cell_range: '', table: '', values_json: '' },
  file: { filename: '', file_base64: '' },
  spreadsheet: { operation: 'read', file_format: 'auto', sheet: '', header_row: true, delimiter: '', path: '', filename: '' },
  linkedin: { access_token: '', author: '', text: '', visibility: 'PUBLIC' },
  bitrix24: { entity: 'lead', operation: 'create', webhook_url: '', item_id: '', fields_json: '', filter_json: '' }
}

/** Новый узел с настройками по умолчанию для своего типа. */
export function createWorkflowNode(type: NodeKind, label: string, position: { x: number; y: number }): WorkflowNode {
  return {
    id: crypto.randomUUID(),
    type,
    position,
    parents: [],
    children: [],
    data: {
      label,
      complexity: type === 'prompt' ? 'simple_text' : undefined,
      max_output_tokens: type === 'prompt' ? 8000 : undefined,
      instructions: type === 'prompt' ? '' : undefined,
      output_format: type === 'prompt' ? '' : undefined,
      request_json: type === 'http_request' ? DEFAULT_HTTP_REQUEST_JSON : undefined,
      condition: type === 'if_else' ? '' : undefined,
      message: type === 'telegram_send' ? '' : undefined,
      chat_id: type === 'telegram_send' ? '' : undefined,
      bot_token: type === 'telegram_send' ? '' : undefined,
      sheet_range: type === 'google_sheets' ? 'Sheet1!A1:Z' : undefined,
      values_json: type === 'google_sheets' ? '[]' : undefined,
      mapping_json: type === 'data_transform' ? '' : undefined,
      sort_direction: type === 'data_transform' ? 'asc' : undefined,
      engine: type === 'sql_query' ? 'postgresql' : undefined,
      query: type === 'sql_query' ? 'SELECT 1 AS ok' : undefined,
      mode: type === 'loop' ? 'for_each' : undefined,
      source: type === 'loop' ? '' : type === 'image' || type === 'audio_transcription' ? 'url' : undefined,
      times: type === 'loop' ? '1' : undefined,
      while_operator: type === 'loop' ? '==' : undefined,
      while_value: type === 'loop' ? '' : undefined,
      amount: type === 'delay' ? '1' : undefined,
      unit: type === 'delay' ? 'seconds' : undefined,
      operation: type === 'google_sheets' ? 'read' : type === 'data_transform' ? 'select' : type === 'yandex_disk' ? 'download' : undefined,
      remote_path: type === 'yandex_disk' ? '' : undefined,
      token: type === 'yandex_disk' ? '' : undefined,
      prompt: type === 'image_generation' || type === 'image_recognition' || type === 'audio_transcription' ? '' : undefined,
      to: type === 'email' ? '' : undefined,
      subject: type === 'email' ? '' : undefined,
      body: type === 'email' ? '' : undefined,
      attach_file: type === 'email' ? false : undefined,
      assignments: ASSIGNABLE_TYPES.has(type) ? [] : undefined,
      ...NEW_NODE_DEFAULTS[type]
    }
  }
}

export const IF_ELSE_CONDITION_PLACEHOLDER = '{{$object.field}} == 12'

export type GraphLink = { source: string; target: string; sourceHandle?: 'true' | 'false' }

export function branchFromHandle(handle?: string | null): 'true' | 'false' | undefined {
  if (!handle) return undefined
  if (handle === 'true' || handle.endsWith('-true')) return 'true'
  if (handle === 'false' || handle.endsWith('-false')) return 'false'
  return undefined
}

export function linksFromNodes(nodes: WorkflowNode[]): GraphLink[] {
  const seen = new Set<string>()
  const links: GraphLink[] = []
  const push = (source: string, target: string, sourceHandle?: 'true' | 'false') => {
    const id = `${source}:${sourceHandle || 'out'}-->${target}`
    if (seen.has(id)) return
    seen.add(id)
    links.push({ source, target, sourceHandle })
  }
  for (const node of nodes) {
    if (node.type === 'if_else') {
      for (const childId of node.true_children || []) push(node.id, childId, 'true')
      for (const childId of node.false_children || []) push(node.id, childId, 'false')
    } else {
      for (const childId of node.children || []) push(node.id, childId)
    }
    for (const parentId of node.parents || []) {
      const parent = nodes.find(item => item.id === parentId)
      if (parent?.type === 'if_else') {
        if ((parent.true_children || []).includes(node.id)) push(parentId, node.id, 'true')
        else if ((parent.false_children || []).includes(node.id)) push(parentId, node.id, 'false')
        else push(parentId, node.id)
      } else {
        push(parentId, node.id)
      }
    }
  }
  return links
}

export function applyLinks(nodes: WorkflowNode[], links: GraphLink[]): WorkflowNode[] {
  const parents = new Map<string, string[]>()
  const children = new Map<string, string[]>()
  const trueChildren = new Map<string, string[]>()
  const falseChildren = new Map<string, string[]>()
  for (const node of nodes) {
    parents.set(node.id, [])
    children.set(node.id, [])
    trueChildren.set(node.id, [])
    falseChildren.set(node.id, [])
  }
  for (const link of links) {
    if (!parents.has(link.target) || !children.has(link.source)) continue
    children.get(link.source)!.push(link.target)
    parents.get(link.target)!.push(link.source)
    if (link.sourceHandle === 'true') trueChildren.get(link.source)!.push(link.target)
    if (link.sourceHandle === 'false') falseChildren.get(link.source)!.push(link.target)
  }
  return nodes.map(node => ({
    ...node,
    parents: parents.get(node.id) || [],
    children: children.get(node.id) || [],
    true_children: node.type === 'if_else' ? trueChildren.get(node.id) || [] : undefined,
    false_children: node.type === 'if_else' ? falseChildren.get(node.id) || [] : undefined
  }))
}

export function resolveNodeId(nodes: WorkflowNode[], raw?: string | null) {
  if (!raw) return ''
  if (nodes.some(node => node.id === raw)) return raw
  const stripped = raw.replace(/-(in|out|true|false)$/, '')
  if (stripped !== raw && nodes.some(node => node.id === stripped)) return stripped
  return raw
}

/** Merge собирает данные из нескольких веток, поэтому ему можно несколько входов. */
export function allowsManyParents(node: WorkflowNode) {
  return node.type === 'data_transform' && node.data.operation === 'merge'
}

export function canConnect(
  nodes: WorkflowNode[],
  links: GraphLink[],
  sourceId: string,
  targetId: string,
  sourceHandle?: string | null
) {
  const source = resolveNodeId(nodes, sourceId)
  const target = resolveNodeId(nodes, targetId)
  const nodeIds = new Set(nodes.map(node => node.id))
  if (!nodeIds.has(source) || !nodeIds.has(target) || source === target) return false
  if (links.some(link => link.source === source && link.target === target)) return false
  const sourceNode = nodes.find(node => node.id === source)
  const targetNode = nodes.find(node => node.id === target)
  const branch = branchFromHandle(sourceHandle)
  if (sourceNode?.type === 'if_else' && !branch) return false
  if (targetNode?.type === 'webhook') return false
  if (
    targetNode
    && SINGLE_INCOMING_TYPES.includes(targetNode.type)
    && !allowsManyParents(targetNode)
    && links.some(link => link.target === target)
  ) return false

  const children = new Map<string, string[]>()
  for (const link of links) {
    children.set(link.source, [...(children.get(link.source) || []), link.target])
  }
  const pending = [target]
  const visited = new Set<string>()
  while (pending.length) {
    const current = pending.pop()!
    if (current === source) return false
    if (visited.has(current)) continue
    visited.add(current)
    pending.push(...(children.get(current) || []))
  }
  return true
}

export function addLink(links: GraphLink[], sourceId: string, targetId: string, sourceHandle?: 'true' | 'false') {
  if (links.some(link => link.source === sourceId && link.target === targetId)) return links
  return [...links, { source: sourceId, target: targetId, sourceHandle }]
}

export function removeLink(links: GraphLink[], sourceId: string, targetId: string) {
  return links.filter(link => !(link.source === sourceId && link.target === targetId))
}

export function dropNodeLinks(links: GraphLink[], nodeId: string) {
  return links.filter(link => link.source !== nodeId && link.target !== nodeId)
}

export function flowEdgesFromLinks(links: GraphLink[]) {
  return links.map(link => ({
    id: `${link.source}-->${link.target}`,
    source: link.source,
    target: link.target,
    sourceHandle: link.sourceHandle ? `${link.source}-${link.sourceHandle}` : `${link.source}-out`,
    targetHandle: `${link.target}-in`,
    type: 'workflow',
    selectable: true,
    deletable: true
  }))
}

export function parseEdgeId(id: string) {
  const separator = '-->'
  const index = id.indexOf(separator)
  if (index === -1) return { source: '', target: '' }
  return { source: id.slice(0, index), target: id.slice(index + separator.length) }
}
