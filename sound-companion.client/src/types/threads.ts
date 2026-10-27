/** One row of `GET /api/threads`. */
export interface ThreadSummary {
  thread_id: string
  title: string | null
  created_at: string
}

/** A Citation parsed back out of a search result: no chunk `id` (decision 69). */
export interface StoredCitation {
  title: string
  section: string
  url: string
  score: number
  license: string
  content: string
}

export interface StoredToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  result: string | null
  citations: StoredCitation[]
}

export interface StoredMessage {
  role: 'user' | 'assistant'
  text: string
  tool_calls?: StoredToolCall[]
}

/** `GET /api/threads/{thread_id}`. */
export interface ThreadDetail {
  thread_id: string
  title: string | null
  messages: StoredMessage[]
}
