import type { NodeKind, WorkflowNode } from '~/types/api'

export const NODE_META: Record<NodeKind, { label: string; caption: string; icon: string; accent: string }> = {
  web_search: { label: 'Поиск в сети', caption: 'Поиск в сети', icon: 'i-lucide-search', accent: '#2bbf8e' },
  prompt: { label: 'Обработка', caption: 'AI Prompt', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  http_request: { label: 'HTTP Request', caption: 'HTTP-запрос', icon: 'i-lucide-globe', accent: '#f59e0b' },
  if_else: { label: 'IF ELSE', caption: 'Условие', icon: 'i-lucide-git-branch', accent: '#e8b84a' },
  telegram_send: { label: 'Telegram', caption: 'Отправить сообщение', icon: 'i-lucide-send', accent: '#2aa8e0' }
}

export const DEFAULT_HTTP_REQUEST_JSON = `{
  "method": "GET",
  "url": "https://api.example.com/users/{{$json.userId}}",
  "headers": {
    "Authorization": "Bearer ..."
  },
  "body": {
    "email": "{{$json.email}}"
  }
}`

export const IF_ELSE_CONDITION_PLACEHOLDER = '{{$json.status}} == "active"'

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
  if (
    (targetNode?.type === 'telegram_send' || targetNode?.type === 'http_request' || targetNode?.type === 'if_else')
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
