import type { WorkflowNode } from '~/types/api'

export const DEFAULT_MAX_OUTPUT_TOKENS = 8000

const CREDITS_COST_MULTIPLIER = 2
const PRICES = {
  simple_text: { miss: 0.44, output: 1.32 },
  complex_text: { miss: 1.32, output: 3.96 }
} as const

function priceFor(node: WorkflowNode) {
  const complex = node.data.complexity === 'complex_text' || String(node.data.model || '').includes('pro')
  return complex ? PRICES.complex_text : PRICES.simple_text
}

function inputTokens(node: WorkflowNode) {
  const text = `${node.data.prompt || ''}\n${node.data.instructions || ''}\n${node.data.output_format || ''}`
  return Math.max(0, Math.ceil([...text].length / 2))
}

function billedCredits(price: { miss: number; output: number }, input: number, output: number) {
  return ((input * price.miss + output * price.output) / 1000) * CREDITS_COST_MULTIPLIER
}

export function promptMaxOutputTokens(node: WorkflowNode) {
  const tokens = Number(node.data.max_output_tokens)
  return Number.isFinite(tokens) && tokens > 0 ? Math.round(tokens) : DEFAULT_MAX_OUTPUT_TOKENS
}

export function promptMaxCredits(node: WorkflowNode) {
  const raw = billedCredits(priceFor(node), inputTokens(node), promptMaxOutputTokens(node))
  if (raw <= 0) return 0
  return Math.ceil(raw)
}

export function maxOutputTokensFromCredits(node: WorkflowNode, credits: number) {
  const price = priceFor(node)
  const input = inputTokens(node)
  const budget = Math.max(0, Number(credits) || 0) / CREDITS_COST_MULTIPLIER
  const inputRaw = (input * price.miss) / 1000
  if (price.output <= 0 || budget <= inputRaw) return 16
  return Math.max(16, Math.floor(((budget - inputRaw) * 1000) / price.output))
}
