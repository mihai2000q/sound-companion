/** Events of the SSE contract (docs/ARCHITECTURE.md). Only the ones the UI handles are typed. */
export type StreamEvent =
  | { type: 'token'; text: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }
  | { type: 'tool_call' | 'tool_result' | 'citations' | 'queries' | 'progress' | 'usage' }

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text: string
  error?: string
}
