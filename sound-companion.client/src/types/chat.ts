/** Events of the SSE contract (docs/ARCHITECTURE.md). Only the ones the UI handles are typed. */
export type StreamEvent =
  | { type: 'token'; text: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }
  | { type: 'citations'; items: Citation[] }
  | { type: 'queries'; items: string[] }
  | { type: 'tool_call'; id: string; name: string; args: Record<string, unknown> }
  | { type: 'tool_result'; id: string; name: string; content: string; durationMs: number }
  | { type: 'progress' | 'usage' }

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

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  error?: string
  stopped?: boolean
  citations?: Citation[]
  queries?: string[]
  toolCalls?: ToolCall[]
}
