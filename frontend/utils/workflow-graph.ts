import type { NodeKind, WorkflowNode } from '~/types/api'

export const NODE_META: Record<NodeKind, { label: string; caption: string; icon: string; accent: string }> = {
  web_search: { label: 'Поиск в сети', caption: 'Web Search', icon: 'i-lucide-search', accent: '#2bbf8e' },
  prompt: { label: 'Обработка', caption: 'AI Prompt', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  telegram_send: { label: 'Telegram', caption: 'Send Message', icon: 'i-lucide-send', accent: '#2aa8e0' }
}

export function canConnect(source: WorkflowNode, target: WorkflowNode) {
  if (source.id === target.id) return false
  if (source.type === 'telegram_send') return false
  if (target.type === 'telegram_send' && (target.parents?.length || 0) >= 1) return false
  if (source.children?.includes(target.id)) return false
  return true
}

export function linkNodes(nodes: WorkflowNode[], sourceId: string, targetId: string) {
  const source = nodes.find(node => node.id === sourceId)
  const target = nodes.find(node => node.id === targetId)
  if (!source || !target || !canConnect(source, target)) return nodes
  return nodes.map((node) => {
    if (node.id === sourceId) {
      return { ...node, children: [...new Set([...(node.children || []), targetId])] }
    }
    if (node.id === targetId) {
      return { ...node, parents: [...new Set([...(node.parents || []), sourceId])] }
    }
    return node
  })
}

export function unlinkNodes(nodes: WorkflowNode[], sourceId: string, targetId: string) {
  return nodes.map((node) => {
    if (node.id === sourceId) {
      return { ...node, children: (node.children || []).filter(id => id !== targetId) }
    }
    if (node.id === targetId) {
      return { ...node, parents: (node.parents || []).filter(id => id !== sourceId) }
    }
    return node
  })
}

export function removeNode(nodes: WorkflowNode[], nodeId: string) {
  return nodes
    .filter(node => node.id !== nodeId)
    .map(node => ({
      ...node,
      parents: (node.parents || []).filter(id => id !== nodeId),
      children: (node.children || []).filter(id => id !== nodeId)
    }))
}

export function flowEdgesFromNodes(nodes: WorkflowNode[]) {
  return nodes.flatMap(node =>
    (node.children || []).map(childId => ({
      id: `${node.id}-->${childId}`,
      source: node.id,
      target: childId
    }))
  )
}

export function parseEdgeId(id: string) {
  const [source, target] = id.split('-->')
  return { source, target }
}
