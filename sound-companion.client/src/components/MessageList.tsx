import { useEffect, useRef } from 'react'
import { chipsFor, labelOf } from '../lib/citations'
import type { ChatMessage, ToolCall } from '../types/chat'

interface Props {
  messages: ChatMessage[]
  streaming: boolean
  onRetry: (botId: string) => void
  onOpenChunk: (messageId: string, chunkId: string) => void
  onSuggest: (text: string) => void
}

const SUGGESTIONS = [
  'What chord is made of the notes D, F and A?',
  'What is the range of a saxophone?',
  'What is the frequency of A4?',
  'What does a B-flat clarinet sound like when it plays a written C?',
]

function Avatar({ role }: { role: ChatMessage['role'] }) {
  return (
    <div className="chat-image avatar avatar-placeholder" aria-hidden="true">
      <div className={`w-8 rounded-full ${role === 'user' ? 'bg-primary text-primary-content' : 'bg-neutral text-neutral-content'}`}>
        <span className="text-xs">{role === 'user' ? 'You' : 'SC'}</span>
      </div>
    </div>
  )
}

/** Shown for a Conversation with no messages: a few questions that start it. */
function EmptyState({ onSuggest }: { onSuggest: Props['onSuggest'] }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center p-4">
      <h2 className="text-2xl font-bold">What would you like to learn?</h2>
      <p className="opacity-70 max-w-md">Ask about music theory or an instrument. Answers cite Wikipedia and Open Music Theory.</p>
      <ul className="flex flex-wrap justify-center gap-2 max-w-xl">
        {SUGGESTIONS.map((question) => (
          <li key={question}>
            <button type="button" className="btn btn-sm btn-outline font-normal h-auto py-2 text-left" onClick={() => onSuggest(question)}>
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function MessageList({ messages, streaming, onRetry, onOpenChunk, onSuggest }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const last = messages.at(-1)
  const typing = streaming && last?.role === 'bot' && last.text === '' && !last.error && !last.toolCalls

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  if (messages.length === 0) return <EmptyState onSuggest={onSuggest} />

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-4">
      {messages.map((message) => {
        if (message.text === '' && !message.error && !message.stopped && !message.toolCalls) return null
        return (
        <div key={message.id} className="flex flex-col gap-1">
          <ToolCards calls={message.toolCalls} />
          {message.text !== '' && (
            <div className={`chat ${message.role === 'user' ? 'chat-end' : 'chat-start'}`}>
              <Avatar role={message.role} />
              <div className="chat-header text-xs opacity-60 mb-1">{message.role === 'user' ? 'You' : 'Sound Companion'}</div>
              <div className={`chat-bubble whitespace-pre-wrap ${message.role === 'user' ? 'chat-bubble-primary' : ''}`}>
                {message.text}
              </div>
            </div>
          )}
          <SourceChips message={message} onOpenChunk={onOpenChunk} />
          {message.stopped && <p className="text-sm opacity-60 px-2">Stopped</p>}
          {message.error && (
            <div role="alert" className="alert alert-error alert-soft">
              <span>{message.error}</span>
              {message === last && !streaming && message.errorCode !== 'budget_exceeded' && (
                <button type="button" className="btn btn-sm" onClick={() => onRetry(message.id)}>
                  Retry
                </button>
              )}
            </div>
          )}
        </div>
        )
      })}
      {typing && (
        <div className="chat chat-start" aria-label="The bot is typing">
          <Avatar role="bot" />
          <div className="chat-bubble">
            <span className="loading loading-dots loading-sm" />
          </div>
        </div>
      )}
      <div ref={end} />
    </div>
  )
}

const SOURCES = [
  { name: 'Wikipedia', url: 'https://en.wikipedia.org' },
  { name: 'Open Music Theory', url: 'https://openmusictheory.github.io' },
]

function SourceChips({ message, onOpenChunk }: { message: ChatMessage; onOpenChunk: Props['onOpenChunk'] }) {
  const chips = message.role === 'bot' ? chipsFor(message.text, message.citations ?? []) : []
  if (chips.length === 0) return null
  return (
    <div className="flex flex-col gap-1 px-2">
      <ul className="flex flex-wrap gap-1">
        {chips.map((chip) => (
          <li key={labelOf(chip)}>
            <button type="button" className="badge badge-outline badge-sm" onClick={() => onOpenChunk(message.id, chip.id)}>
              {labelOf(chip)}
            </button>
          </li>
        ))}
      </ul>
      <p className="text-xs opacity-60">
        Sources:{' '}
        {SOURCES.map((source, i) => (
          <span key={source.name}>
            {i > 0 && ' and '}
            <a className="link" href={source.url} target="_blank" rel="noreferrer">
              {source.name}
            </a>
          </span>
        ))}
        , CC BY-SA 4.0
      </p>
    </div>
  )
}

const STATUS = {
  running: { label: 'Running', badge: 'badge-info' },
  done: { label: 'Done', badge: 'badge-success' },
  error: { label: 'Error', badge: 'badge-error' },
  stopped: { label: 'Stopped', badge: 'badge-warning' },
}

function ToolCards({ calls }: { calls: ToolCall[] | undefined }) {
  if (!calls?.length) return null
  return (
    <ul className="flex flex-col gap-1 px-2">
      {calls.map((call) => (
        <ToolCard key={call.id} call={call} />
      ))}
    </ul>
  )
}

/** A DaisyUI `collapse` on a native `<details>`: open while the call runs or failed, closed once it is done. */
function ToolCard({ call }: { call: ToolCall }) {
  const status = STATUS[call.status]
  return (
    <li>
      <details
        className={`collapse collapse-arrow card-border bg-base-100 ${call.status === 'error' ? 'border-error' : 'border-base-300'}`}
        open={call.status === 'running' || call.status === 'error'}
      >
        <summary className="collapse-title min-h-0 py-2 pr-10">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium break-all">{call.name}</span>
            <span className={`badge badge-sm badge-soft ${status.badge}`}>
              {call.status === 'running' && <span className="loading loading-spinner loading-xs" />}
              {status.label}
            </span>
            {call.durationMs !== undefined && <span className="text-xs opacity-60">{call.durationMs} ms</span>}
          </span>
        </summary>
        <div className="collapse-content flex flex-col gap-1 min-w-0">
          <pre className="text-xs whitespace-pre-wrap break-all">{JSON.stringify(call.args)}</pre>
          {call.content !== undefined && (
            <pre className="text-xs whitespace-pre-wrap break-all max-h-40 overflow-y-auto">{call.content}</pre>
          )}
        </div>
      </details>
    </li>
  )
}
