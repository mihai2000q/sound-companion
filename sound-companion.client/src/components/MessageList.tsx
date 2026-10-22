import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../types/chat'

interface Props {
  messages: ChatMessage[]
  streaming: boolean
  onRetry: (botId: string) => void
}

export function MessageList({ messages, streaming, onRetry }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const last = messages.at(-1)
  const typing = streaming && last?.role === 'bot' && last.text === '' && !last.error

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-4">
      {messages.map((message) => {
        if (message.text === '' && !message.error && !message.stopped) return null
        return (
        <div key={message.id} className="flex flex-col gap-1">
          {message.text !== '' && (
            <div className={`chat ${message.role === 'user' ? 'chat-end' : 'chat-start'}`}>
              <div className={`chat-bubble whitespace-pre-wrap ${message.role === 'user' ? 'chat-bubble-primary' : ''}`}>
                {message.text}
              </div>
            </div>
          )}
          {message.stopped && <p className="text-sm opacity-60 px-2">Stopped</p>}
          {message.error && (
            <div role="alert" className="alert alert-error alert-soft">
              <span>{message.error}</span>
              {message === last && !streaming && (
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
          <div className="chat-bubble">
            <span className="loading loading-dots loading-sm" />
          </div>
        </div>
      )}
      <div ref={end} />
    </div>
  )
}
