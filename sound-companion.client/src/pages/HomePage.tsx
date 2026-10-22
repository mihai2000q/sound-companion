import { useState } from 'react'
import { Composer } from '../components/Composer'
import { Inspector, type ChunkFocus } from '../components/Inspector'
import { MessageList } from '../components/MessageList'
import { useChatStream } from '../hooks/useChatStream'

export function HomePage() {
  const { messages, streaming, fieldError, clearFieldError, send, retry, stop, newChat } = useChatStream()
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focus, setFocus] = useState<ChunkFocus | null>(null)

  // the latest answer with a search, unless a chip picked another one
  const inspected =
    messages.find((message) => message.id === selectedId) ??
    messages.findLast((message) => message.role === 'bot' && (message.citations || message.queries))

  function openChunk(messageId: string, chunkId: string) {
    setSelectedId(messageId)
    setFocus({ messageId, chunkId })
    setInspectorOpen(true)
  }

  function startNewChat() {
    newChat()
    setSelectedId(null)
    setFocus(null)
    setInspectorOpen(false)
  }

  return (
    <main className="h-screen flex flex-col bg-base-200">
      <header className="flex items-center justify-between p-4 border-b border-base-300">
        <h1 className="text-xl font-bold">Sound Companion</h1>
        <div className="flex gap-2">
          <button type="button" className="btn btn-sm" aria-expanded={inspectorOpen} onClick={() => setInspectorOpen((open) => !open)}>
            Inspector
          </button>
          <button type="button" className="btn btn-sm" disabled={streaming} onClick={startNewChat}>
            New chat
          </button>
        </div>
      </header>
      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-w-0 max-w-3xl mx-auto flex flex-col bg-base-100">
          <MessageList messages={messages} streaming={streaming} onRetry={retry} onOpenChunk={openChunk} />
          <Composer disabled={streaming} error={fieldError} onSend={send} onEdit={clearFieldError} onStop={stop} />
        </div>
        <Inspector message={inspected} open={inspectorOpen} focus={focus} onClose={() => setInspectorOpen(false)} />
      </div>
    </main>
  )
}
