import { useState } from 'react'
import { EventSourceParserStream } from 'eventsource-parser/stream'
import type { ChatMessage, StreamEvent } from '../types/chat'

async function* readEvents(response: Response): AsyncGenerator<StreamEvent> {
  const stream = response.body!
    .pipeThrough(new TextDecoderStream())
    .pipeThrough(new EventSourceParserStream())
  for await (const message of stream) {
    yield JSON.parse(message.data) as StreamEvent
  }
}

function errorMessage(response: Response): string {
  if (response.status === 422) return 'That message could not be sent. Check it and try again.'
  return `The server answered ${response.status}. Please try again.`
}

export function useChatStream() {
  const [threadId] = useState(() => crypto.randomUUID())
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)

  function updateBot(id: string, change: (message: ChatMessage) => ChatMessage) {
    setMessages((all) => all.map((message) => (message.id === id ? change(message) : message)))
  }

  async function send(text: string) {
    const botId = crypto.randomUUID()
    setMessages((all) => [
      ...all,
      { id: crypto.randomUUID(), role: 'user', text },
      { id: botId, role: 'bot', text: '' },
    ])
    setStreaming(true)
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, message: text }),
      })
      if (!response.ok) throw new Error(errorMessage(response))
      for await (const event of readEvents(response)) {
        if (event.type === 'token') {
          updateBot(botId, (message) => ({ ...message, text: message.text + event.text }))
        } else if (event.type === 'error') {
          throw new Error(event.message)
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The connection was lost.'
      updateBot(botId, (bot) => ({ ...bot, error: message }))
    } finally {
      setStreaming(false)
    }
  }

  return { messages, streaming, send }
}
