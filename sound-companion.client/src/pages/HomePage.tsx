import { Composer } from '../components/Composer'
import { MessageList } from '../components/MessageList'
import { useChatStream } from '../hooks/useChatStream'

export function HomePage() {
  const { messages, streaming, send } = useChatStream()

  return (
    <main className="h-screen flex flex-col bg-base-200">
      <h1 className="text-xl font-bold p-4 border-b border-base-300">Sound Companion</h1>
      <div className="flex-1 min-h-0 w-full max-w-3xl mx-auto flex flex-col bg-base-100">
        <MessageList messages={messages} streaming={streaming} />
        <Composer disabled={streaming} onSend={send} />
      </div>
    </main>
  )
}
