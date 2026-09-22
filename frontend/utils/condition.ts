/** Разбор строки условия IF ELSE в левую часть, оператор и правую часть.

Сохранённый граф по-прежнему держит одно поле `condition`, например `{{$json.score}} >= 0.8`.
Порядок операторов как у бэкенда: длинные раньше коротких, без === / !==.
*/

export const CONDITION_OPERATORS = ['>=', '<=', '==', '!=', '>', '<'] as const

export type ConditionOperator = (typeof CONDITION_OPERATORS)[number]

export type ConditionParts = {
  left: string
  operator: ConditionOperator
  right: string
}

export function splitCondition(expression: string): ConditionParts | null {
  const expr = expression ?? ''
  let quote: string | null = null
  for (let index = 0; index < expr.length; index += 1) {
    const char = expr[index]
    if (quote) {
      if (char === '\\' && index + 1 < expr.length) {
        index += 1
        continue
      }
      if (char === quote) quote = null
      continue
    }
    if (char === '"' || char === "'") {
      quote = char
      continue
    }
    for (const operator of CONDITION_OPERATORS) {
      if (!expr.startsWith(operator, index)) continue
      const left = expr.slice(0, index).trim()
      const right = expr.slice(index + operator.length).trim()
      if (!left || !right) return null
      return { left, operator, right }
    }
  }
  return null
}

export function joinCondition(left: string, operator: string, right: string): string {
  const trimmedLeft = left.trim()
  const trimmedRight = right.trim()
  if (!trimmedLeft && !trimmedRight) return ''
  return `${trimmedLeft} ${operator} ${trimmedRight}`.trim()
}
