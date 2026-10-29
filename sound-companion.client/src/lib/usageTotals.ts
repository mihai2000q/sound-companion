import type { ModelRow } from '../types/monitoring'

export interface UsageTotal {
  calls: number
  prompt_tokens: number
  completion_tokens: number
  cost_credits: number
}

const empty = (): UsageTotal => ({ calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_credits: 0 })

function add(total: UsageTotal, row: ModelRow) {
  total.calls += row.calls
  total.prompt_tokens += row.prompt_tokens
  total.completion_tokens += row.completion_tokens
  total.cost_credits += row.cost_credits
}

/** Every purpose of one model stacked (answer, rewrite, embed, eval), the most expensive model first, and the sum of all of them. */
export function totalsPerModel(rows: ModelRow[]): { models: ({ model: string } & UsageTotal)[]; all: UsageTotal } {
  const byModel = new Map<string, UsageTotal>()
  const all = empty()
  for (const row of rows) {
    const total = byModel.get(row.model) ?? empty()
    add(total, row)
    add(all, row)
    byModel.set(row.model, total)
  }
  const models = [...byModel].map(([model, total]) => ({ model, ...total })).sort((a, b) => b.cost_credits - a.cost_credits)
  return { models, all }
}
