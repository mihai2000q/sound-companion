import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { useChatStream } from '../hooks/useChatStream'
import { threadKeys } from '../queries/threads'
import type { ChatMessage, Usage } from '../types/chat'
import { Composer } from './Composer'
import { Inspector, type ChunkFocus } from './Inspector'
import { MessageList } from './MessageList'
import { UsageBadge } from './UsageBadge'

interface Props {
  threadId: string
  initialMessages: ChatMessage[]
  usage: Usage | null
  setUsage: Dispatch<SetStateAction<Usage | null>>
  onStreamingChange: (streaming: boolean) => void
  onNew: () => void
  onOpenSidebar: () => void
}

/** One Conversation: header, messages, composer and inspector. The page gives it a `key` of its `threadId`, so a
 *  switch starts a fresh instance (messages, selection and inspector are reset). */
export function Conversation({ threadId, initialMessages, usage, setUsage, onStreamingChange, onNew, onOpenSidebar }: Props) {
  const { messages, streaming, fieldError, clearFieldError, send, retry, stop } = useChatStream(threadId, initialMessages, setUsage)
  const queryClient = useQueryClient()
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focus, setFocus] = useState<ChunkFocus | null>(null)

  useEffect(() => {
    onStreamingChange(streaming)
    return () => onStreamingChange(false)
  }, [streaming, onStreamingChange])

  // the latest answer with a search, unless a chip picked another one
  const inspected =
    messages.find((message) => message.id === selectedId) ??
    messages.findLast((message) => message.role === 'bot' && (message.citations || message.queries))

  function openChunk(messageId: string, chunkId: string) {
    setSelectedId(messageId)
    setFocus({ messageId, chunkId })
    setInspectorOpen(true)
  }

  /** The server writes the Conversation on its first request, so the list is read again when an answer is over. */
  async function sendAndRefresh(text: string) {
    const accepted = await send(text)
    if (accepted) await queryClient.invalidateQueries({ queryKey: threadKeys.list() })
    return accepted
  }

  return (
    <div className="flex-1 min-w-0 flex flex-col">
      <header className="flex items-center justify-between gap-2 p-4 border-b border-base-300">
        <div className="flex items-center gap-2 min-w-0">
          <button type="button" className="btn btn-sm lg:hidden" onClick={onOpenSidebar}>
            Conversations
          </button>
          <h1 className="text-xl font-bold truncate max-sm:hidden">Sound Companion</h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {usage && <UsageBadge usage={usage} />}
          <button type="button" className="btn btn-sm" aria-expanded={inspectorOpen} onClick={() => setInspectorOpen((open) => !open)}>
            Inspector
          </button>
          <Link to="/monitoring" className="btn btn-sm">
            Monitoring
          </Link>
          <button type="button" className="btn btn-sm lg:hidden" disabled={streaming} onClick={onNew}>
            New Conversation
          </button>
        </div>
      </header>
      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-w-0 max-w-3xl mx-auto flex flex-col bg-base-100">
          <MessageList messages={messages} streaming={streaming} onRetry={retry} onOpenChunk={openChunk} />
          <Composer disabled={streaming} error={fieldError} onSend={sendAndRefresh} onEdit={clearFieldError} onStop={stop} />
        </div>
        <Inspector message={inspected} open={inspectorOpen} focus={focus} onClose={() => setInspectorOpen(false)} />
      </div>
    </div>
  )
}
