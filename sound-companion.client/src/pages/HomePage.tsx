import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { AppBar } from '../components/AppBar'
import { Conversation } from '../components/Conversation'
import { useChatActivity } from '../state/chatActivity'
import { toChatMessages } from '../lib/conversation'
import { threadQueries } from '../queries/threads'
import type { Usage } from '../types/chat'
import { Spinner } from '@/components/ui/spinner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

/** What the chat route of the server accepts (a lowercase UUID). */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

/** The selected Conversation is the `c` parameter of the URL, so a reload restores it. Without a valid one the page
 *  starts a new Conversation: the id is made here, and the server writes the Conversation on its first message. */
export function HomePage() {
  const [params, setParams] = useSearchParams()
  const param = params.get('c')
  const threadId = param && UUID.test(param) ? param : null
  const [usage, setUsage] = useState<Usage | null>(null)
  const { setStreaming } = useChatActivity()

  useEffect(() => {
    if (!threadId) setParams({ c: crypto.randomUUID() }, { replace: true })
  }, [threadId, setParams])

  if (!threadId) return null

  return (
    <div className="flex h-full min-h-0">
      <Chat key={threadId} threadId={threadId} usage={usage} setUsage={setUsage} onStreamingChange={setStreaming} />
    </div>
  )
}

type ChatProps = Omit<React.ComponentProps<typeof Conversation>, 'initialMessages'>

/** Reads the stored messages once, then hands them to the Conversation (which keeps its own state from there on). */
function Chat(props: ChatProps) {
  const { data, error, isPending, refetch } = useQuery(threadQueries.detail(props.threadId))
  if (isPending)
    return (
      <div className="flex-1 min-w-0 flex flex-col">
        <AppBar />
        <div className="flex-1 grid place-items-center bg-background"><Spinner className="size-6" /></div>
      </div>
    )
  if (error)
    return (
      <div className="flex-1 min-w-0 flex flex-col">
        <AppBar />
        <div className="flex-1 grid place-items-center bg-background">
          <Alert variant="destructive" className="flex w-auto flex-col items-start gap-2">
            <span>This Conversation could not be loaded.</span>
            <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          </Alert>
        </div>
      </div>
    )
  return <Conversation {...props} initialMessages={toChatMessages(data?.messages ?? [])} />
}
