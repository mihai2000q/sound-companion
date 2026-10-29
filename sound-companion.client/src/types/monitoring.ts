export interface DailyRow {
  day: string
  requests: number
  errors: number
  error_rate: number
  avg_ms: number
  p95_ms: number
  prompt_tokens: number
  completion_tokens: number
  cost_credits: number
}

export interface ToolRow {
  tool: string
  calls: number
  errors: number
  avg_ms: number
}

export interface ModelRow {
  purpose: string
  model: string
  calls: number
  prompt_tokens: number
  completion_tokens: number
  cost_credits: number
}

export interface Monitoring {
  daily: DailyRow[]
  tools: ToolRow[]
  models: ModelRow[]
}
