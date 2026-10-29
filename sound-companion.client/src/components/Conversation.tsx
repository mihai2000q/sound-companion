import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useChatStream } from '../hooks/useChatStream'
import { threadKeys } from '../queries/threads'
import type { ChatMessage, Usage } from '../types/chat'
import { useChatActivity } from '../state/chatActivity'
import { AppBar } from './AppBar'
import { Composer } from './Composer'
import { Inspector, type ChunkFocus } from './Inspector'
import { MessageList } from './MessageList'
import { UsageBadge } from './UsageBadge'
import { Button } from '@/components/ui/button'

interface Props {
  threadId: string
  initialMessages: ChatMessage[]
  usage: Usage | null
  setUsage: Dispatch<SetStateAction<Usage | null>>
  onStreamingChange: (streaming: boolean) => void
}

/** One Conversation: app bar, messages, composer and inspector. The page gives it a `key` of its `threadId`, so a
 *  switch starts a fresh instance (messages, selection and inspector are reset). */
export function Conversation({ threadId, initialMessages, usage, setUsage, onStreamingChange }: Props) {
  const { messages, streaming, fieldError, clearFieldError, send, retry, stop } = useChatStream(threadId, initialMessages, setUsage)
  const queryClient = useQueryClient()
  const { inspectorOpen, setInspectorOpen } = useChatActivity()
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
      <AppBar>
        {usage && <UsageBadge usage={usage} />}
        <Button type="button" variant="outline" size="sm" aria-expanded={inspectorOpen} onClick={() => setInspectorOpen(!inspectorOpen)}>
          Inspector
        </Button>
      </AppBar>
      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-w-0 max-w-3xl mx-auto flex flex-col bg-background">
          <MessageList messages={messages} streaming={streaming} onRetry={retry} onOpenChunk={openChunk} onSuggest={(text) => void sendAndRefresh(text)} />
          <Composer disabled={streaming} error={fieldError} onSend={sendAndRefresh} onEdit={clearFieldError} onStop={stop} />
        </div>
        <Inspector message={inspected} open={inspectorOpen} focus={focus} onClose={() => setInspectorOpen(false)} />
      </div>
    </div>
  )
}
