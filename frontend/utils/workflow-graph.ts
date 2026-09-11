import type { NodeKind, WorkflowNode } from '~/types/api'

export const NODE_META: Record<NodeKind, { label: string; caption: string; icon: string; accent: string }> = {
  web_search: { label: 'Поиск в сети', caption: 'Поиск в сети', icon: 'i-lucide-search', accent: '#2bbf8e' },
  prompt: { label: 'Обработка', caption: 'AI Prompt', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  telegram_send: { label: 'Telegram', caption: 'Отправить сообщение', icon: 'i-lucide-send', accent: '#2aa8e0' }
}

export type GraphLink = { source: string; target: string }

export function linksFromNodes(nodes: WorkflowNode[]): GraphLink[] {
  const seen = new Set<string>()
  const links: GraphLink[] = []
  for (const node of nodes) {
    for (const childId of node.children || []) {
      const id = `${node.id}-->${childId}`
      if (seen.has(id)) continue
      seen.add(id)
      links.push({ source: node.id, target: childId })
    }
    for (const parentId of node.parents || []) {
      const id = `${parentId}-->${node.id}`
      if (seen.has(id)) continue
      seen.add(id)
      links.push({ source: parentId, target: node.id })
    }
  }
  return links
}

export function applyLinks(nodes: WorkflowNode[], links: GraphLink[]): WorkflowNode[] {
  const parents = new Map<string, string[]>()
  const children = new Map<string, string[]>()
  for (const node of nodes) {
    parents.set(node.id, [])
    children.set(node.id, [])
  }
  for (const link of links) {
    if (!parents.has(link.target) || !children.has(link.source)) continue
    children.get(link.source)!.push(link.target)
    parents.get(link.target)!.push(link.source)
  }
  return nodes.map(node => ({
    ...node,
    parents: parents.get(node.id) || [],
    children: children.get(node.id) || []
  }))
}

export function resolveNodeId(nodes: WorkflowNode[], raw?: string | null) {
  if (!raw) return ''
  if (nodes.some(node => node.id === raw)) return raw
  const stripped = raw.replace(/-(in|out)$/, '')
  if (stripped !== raw && nodes.some(node => node.id === stripped)) return stripped
  return raw
}

export function canConnect(nodes: WorkflowNode[], links: GraphLink[], sourceId: string, targetId: string) {
  const source = resolveNodeId(nodes, sourceId)
  const target = resolveNodeId(nodes, targetId)
  const nodeIds = new Set(nodes.map(node => node.id))
  if (!nodeIds.has(source) || !nodeIds.has(target) || source === target) return false
  if (links.some(link => link.source === source && link.target === target)) return false
  const targetNode = nodes.find(node => node.id === target)
  if (targetNode?.type === 'telegram_send' && links.some(link => link.target === target)) return false

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

export function addLink(links: GraphLink[], sourceId: string, targetId: string) {
  if (links.some(link => link.source === sourceId && link.target === targetId)) return links
  return [...links, { source: sourceId, target: targetId }]
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
    sourceHandle: `${link.source}-out`,
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
