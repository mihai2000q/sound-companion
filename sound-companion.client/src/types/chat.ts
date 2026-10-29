/** Events of the SSE contract (docs/ARCHITECTURE.md). Only the ones the UI handles are typed. */
export type StreamEvent =
  | { type: 'token'; text: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }
  | { type: 'citations'; items: Citation[] }
  | { type: 'queries'; items: string[] }
  | { type: 'tool_call'; id: string; name: string; args: Record<string, unknown> }
  | { type: 'tool_result'; id: string; name: string; content: string; durationMs: number }
  | { type: 'usage'; promptTokens: number; completionTokens: number; cost: number; totalSpend: number; warning: boolean }

/** A retrieved chunk, from stored metadata. `id` is the chunk id, `content` the chunk text. */
export interface Citation {
  id: string
  title: string
  section: string
  url: string
  score: number
  license: string
  content: string
}

/** `stopped` is a call whose result never came (cancelled, failed or lost connection). */
export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  status: 'running' | 'done' | 'error' | 'stopped'
  content?: string
  durationMs?: number
}

/** Credits spent: `cost` by the current turn so far, `totalSpend` by everything (the database sum).
 * `warning` is set at or above the soft cap. */
export interface Usage {
  cost: number
  totalSpend: number
  warning: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  error?: string
  errorCode?: string
  stopped?: boolean
  citations?: Citation[]
  queries?: string[]
  toolCalls?: ToolCall[]
}
