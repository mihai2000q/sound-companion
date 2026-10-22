import { useRef, useState } from 'react'
import { EventSourceParserStream } from 'eventsource-parser/stream'
import type { ChatMessage, StreamEvent, ToolCall } from '../types/chat'

/** The server pings every 15 s, so this much silence means the connection is dead (a proxy may never close it). */
const IDLE_MS = 45_000

/** Aborts the request after IDLE_MS without a chunk. `reset` is called on every chunk, `stop` when done. */
function idleWatchdog(controller: AbortController) {
  let timer: ReturnType<typeof setTimeout>
  const reset = () => {
    clearTimeout(timer)
    timer = setTimeout(() => controller.abort(), IDLE_MS)
  }
  return { reset, stop: () => clearTimeout(timer) }
}

async function* readEvents(response: Response, onChunk: () => void): AsyncGenerator<StreamEvent> {
  const activity = new TransformStream<string, string>({
    transform(chunk, controller) {
      onChunk()
      controller.enqueue(chunk)
    },
  })
  const stream = response.body!
    .pipeThrough(new TextDecoderStream())
    .pipeThrough(activity)
    .pipeThrough(new EventSourceParserStream())
  for await (const message of stream) {
    yield JSON.parse(message.data) as StreamEvent
  }
}

/** The music tools return `{ error, message }` for bad input. */
function isToolError(content: string): boolean {
  try {
    const parsed = JSON.parse(content)
    return typeof parsed?.error === 'string' && typeof parsed?.message === 'string'
  } catch {
    return false
  }
}

function withResult(calls: ToolCall[] | undefined, event: Extract<StreamEvent, { type: 'tool_result' }>): ToolCall[] {
  const result = {
    status: isToolError(event.content) ? ('error' as const) : ('done' as const),
    content: event.content,
    durationMs: event.durationMs,
  }
  const all = calls ?? []
  if (!all.some((call) => call.id === event.id)) return [...all, { id: event.id, name: event.name, args: {}, ...result }]
  return all.map((call) => (call.id === event.id ? { ...call, ...result } : call))
}

/** No card stays on "running" once the stream is over. */
function settled(message: ChatMessage): ChatMessage {
  if (!message.toolCalls?.some((call) => call.status === 'running')) return message
  return { ...message, toolCalls: message.toolCalls.map((call) => (call.status === 'running' ? { ...call, status: 'stopped' } : call)) }
}

const CONNECTION_LOST = 'The connection was lost.'

export interface FieldError {
  field: string
  message: string
}

/** FastAPI's 422 body: `detail` is a list of `{ loc: ['body', field], msg }`. */
async function fieldErrorOf(response: Response): Promise<FieldError> {
  const detail = (await response.json().catch(() => null))?.detail?.[0]
  return { field: detail?.loc?.at(-1) ?? 'message', message: detail?.msg ?? 'The input is not valid.' }
}

export function useChatStream() {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID())
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [fieldError, setFieldError] = useState<FieldError | null>(null)
  const stopRef = useRef<(() => void) | null>(null)

  function updateMessage(id: string, change: (message: ChatMessage) => ChatMessage) {
    setMessages((all) => all.map((message) => (message.id === id ? change(message) : message)))
  }

  function fail(botId: string, error: string) {
    updateMessage(botId, (message) => settled({ ...message, error }))
  }

  async function consume(response: Response, botId: string, onChunk: () => void, stopped: () => boolean) {
    let finished = false
    try {
      for await (const event of readEvents(response, onChunk)) {
        if (event.type === 'token') {
          updateMessage(botId, (message) => ({ ...message, text: message.text + event.text }))
        } else if (event.type === 'citations') {
          // a turn can search more than once, so the chunks of every search are kept
          updateMessage(botId, (message) => ({ ...message, citations: [...(message.citations ?? []), ...event.items] }))
        } else if (event.type === 'queries') {
          updateMessage(botId, (message) => ({ ...message, queries: [...(message.queries ?? []), ...event.items] }))
        } else if (event.type === 'tool_call') {
          const call: ToolCall = { id: event.id, name: event.name, args: event.args, status: 'running' }
          updateMessage(botId, (message) => ({ ...message, toolCalls: [...(message.toolCalls ?? []), call] }))
        } else if (event.type === 'tool_result') {
          updateMessage(botId, (message) => ({ ...message, toolCalls: withResult(message.toolCalls, event) }))
        } else if (event.type === 'error') {
          return fail(botId, event.message)
        } else if (event.type === 'done') {
          finished = true
        }
      }
      if (!finished) fail(botId, CONNECTION_LOST)
    } catch {
      if (!stopped()) fail(botId, CONNECTION_LOST)
    }
  }

  /** Streams the answer into `botId`. Resolves to false when the server rejected the input (422). */
  async function ask(text: string, userId: string, botId: string): Promise<boolean> {
    setStreaming(true)
    const controller = new AbortController()
    const watchdog = idleWatchdog(controller)
    watchdog.reset()
    let stopped = false
    stopRef.current = () => {
      stopped = true
      controller.abort()
    }
    try {
      const response = await fetch('/api/chat', {
        signal: controller.signal,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, message: text }),
      })
      if (response.status === 422) {
        setFieldError(await fieldErrorOf(response))
        setMessages((all) => all.filter((message) => message.id !== userId && message.id !== botId))
        return false
      }
      if (!response.ok) fail(botId, `The server answered ${response.status}. Please try again.`)
      else await consume(response, botId, watchdog.reset, () => stopped)
    } catch {
      if (!stopped) fail(botId, CONNECTION_LOST)
    } finally {
      watchdog.stop()
      stopRef.current = null
      if (stopped) updateMessage(botId, (message) => settled({ ...message, stopped: true }))
      setStreaming(false)
    }
    return true
  }

  /** Resolves when the answer has finished, with false when the message was rejected and should stay in the composer. */
  function send(text: string): Promise<boolean> {
    const userId = crypto.randomUUID()
    const botId = crypto.randomUUID()
    setFieldError(null)
    setMessages((all) => [
      ...all,
      { id: userId, role: 'user', text },
      { id: botId, role: 'bot', text: '' },
    ])
    return ask(text, userId, botId)
  }

  /** Asks the question before the failed bot message again, and drops the partial answer. */
  function retry(botId: string) {
    const index = messages.findIndex((message) => message.id === botId)
    const question = messages[index - 1]
    if (!question) return
    updateMessage(botId, (message) => ({ ...message, text: '', error: undefined, stopped: undefined, citations: undefined, queries: undefined, toolCalls: undefined }))
    void ask(question.text, question.id, botId)
  }

  /** Aborts the request. The partial answer stays and is marked as stopped. */
  function stop() {
    stopRef.current?.()
  }

  function newChat() {
    setThreadId(crypto.randomUUID())
    setMessages([])
    setFieldError(null)
  }

  return { messages, streaming, fieldError, clearFieldError: () => setFieldError(null), send, retry, stop, newChat }
}
