import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../types/chat'

interface Props {
  messages: ChatMessage[]
  streaming: boolean
}

export function MessageList({ messages, streaming }: Props) {
  const end = useRef<HTMLDivElement>(null)
  const last = messages.at(-1)
  const typing = streaming && last?.role === 'bot' && last.text === '' && !last.error

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-4">
      {messages.map((message) => {
        if (message.role === 'bot' && message.text === '' && !message.error) return null
        return (
          <div key={message.id} className={`chat ${message.role === 'user' ? 'chat-end' : 'chat-start'}`}>
            {message.text !== '' && (
              <div className={`chat-bubble whitespace-pre-wrap ${message.role === 'user' ? 'chat-bubble-primary' : ''}`}>
                {message.text}
              </div>
            )}
            {message.error && (
              <div role="alert" className="alert alert-error alert-soft mt-1">
                {message.error}
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
