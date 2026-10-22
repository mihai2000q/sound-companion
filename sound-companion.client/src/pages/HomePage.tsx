import { Composer } from '../components/Composer'
import { MessageList } from '../components/MessageList'
import { useChatStream } from '../hooks/useChatStream'

export function HomePage() {
  const { messages, streaming, fieldError, clearFieldError, send, retry, stop, newChat } = useChatStream()

  return (
    <main className="h-screen flex flex-col bg-base-200">
      <header className="flex items-center justify-between p-4 border-b border-base-300">
        <h1 className="text-xl font-bold">Sound Companion</h1>
        <button type="button" className="btn btn-sm" disabled={streaming} onClick={newChat}>
          New chat
        </button>
      </header>
      <div className="flex-1 min-h-0 w-full max-w-3xl mx-auto flex flex-col bg-base-100">
        <MessageList messages={messages} streaming={streaming} onRetry={retry} />
        <Composer disabled={streaming} error={fieldError} onSend={send} onEdit={clearFieldError} onStop={stop} />
      </div>
    </main>
  )
}
