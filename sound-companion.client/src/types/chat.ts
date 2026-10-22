/** Events of the SSE contract (docs/ARCHITECTURE.md). Only the ones the UI handles are typed. */
export type StreamEvent =
  | { type: 'token'; text: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }
  | { type: 'citations'; items: Citation[] }
  | { type: 'queries'; items: string[] }
  | { type: 'tool_call' | 'tool_result' | 'progress' | 'usage' }

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

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  error?: string
  stopped?: boolean
  citations?: Citation[]
  queries?: string[]
}
