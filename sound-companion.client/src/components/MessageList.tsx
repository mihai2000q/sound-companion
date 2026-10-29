import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { chipsFor, labelOf } from '../lib/citations'
import type { ChatMessage, ToolCall } from '../types/chat'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import { Spinner } from '@/components/ui/spinner'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Message } from './Message'

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

/** Shown for a Conversation with no messages: a few questions that start it. */
function EmptyState({ onSuggest }: { onSuggest: Props['onSuggest'] }) {
  return (
    <Empty className="flex-1">
      <EmptyHeader>
        <div className="staff w-full max-w-lg py-3">
          <EmptyTitle className="mx-auto w-fit bg-background px-4 font-serif text-3xl font-medium tracking-tight">What would you like to learn?</EmptyTitle>
        </div>
        <EmptyDescription>Ask about music theory or an instrument. Answers cite Wikipedia and Open Music Theory.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent className="max-w-xl">
        <ul className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((question) => (
            <li key={question}>
              <Button type="button" variant="outline" size="sm" className="h-auto py-2 text-left font-normal whitespace-normal" onClick={() => onSuggest(question)}>
                {question}
              </Button>
            </li>
          ))}
        </ul>
      </EmptyContent>
    </Empty>
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
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-3 p-4">
      {messages.map((message) => {
        if (message.text === '' && !message.error && !message.stopped && !message.toolCalls) return null
        return (
        <div key={message.id} className="flex flex-col gap-1">
          <ToolCards calls={message.toolCalls} />
          {message.text !== '' && (
            <Message role={message.role}>{message.text}</Message>
          )}
          <SourceChips message={message} onOpenChunk={onOpenChunk} />
          {message.stopped && <p className="text-sm text-muted-foreground px-2">Stopped</p>}
          {message.error && (
            <Alert variant="destructive" className="flex items-center justify-between gap-2">
              <span>{message.error}</span>
              {message === last && !streaming && message.errorCode !== 'budget_exceeded' && (
                <Button type="button" variant="outline" size="sm" onClick={() => onRetry(message.id)}>
                  Retry
                </Button>
              )}
            </Alert>
          )}
        </div>
        )
      })}
      {typing && (
        <Message role="bot" label="The bot is typing">
          <Spinner />
        </Message>
      )}
      <div ref={end} />
      </div>
    </ScrollArea>
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
            <Badge asChild variant="outline" className="border-brass/60 bg-accent text-accent-foreground hover:bg-brass/30">
              <button type="button" onClick={() => onOpenChunk(message.id, chip.id)}>
                {labelOf(chip)}
              </button>
            </Badge>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        Sources:{' '}
        {SOURCES.map((source, i) => (
          <span key={source.name}>
            {i > 0 && ' and '}
            <a className="underline underline-offset-2 hover:text-foreground" href={source.url} target="_blank" rel="noreferrer">
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
  running: { label: 'Running', badge: 'text-sky-700 dark:text-sky-300' },
  done: { label: 'Done', badge: 'text-green-700 dark:text-green-300' },
  error: { label: 'Error', badge: 'text-destructive' },
  stopped: { label: 'Stopped', badge: 'text-amber-700 dark:text-amber-300' },
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

/** A `collapsible`: open while the call runs or failed, closed once it is done (a click still toggles it). */
function ToolCard({ call }: { call: ToolCall }) {
  const status = STATUS[call.status]
  const auto = call.status === 'running' || call.status === 'error'
  const [open, setOpen] = useState(auto)
  const [seen, setSeen] = useState(call.status)
  if (seen !== call.status) {
    // the status moved on: follow it again, whatever was clicked before
    setSeen(call.status)
    setOpen(auto)
  }
  return (
    <li>
      <Collapsible open={open} onOpenChange={setOpen} className={cn('rounded-lg border bg-card', call.status === 'error' && 'border-destructive')}>
        <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 px-4 py-2 text-left">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium break-all">{call.name}</span>
            <Badge variant="secondary" className={status.badge}>
              {call.status === 'running' && <Spinner className="size-3" />}
              {status.label}
            </Badge>
            {call.durationMs !== undefined && <span className="text-xs text-muted-foreground">{call.durationMs} ms</span>}
          </span>
          <ChevronDown className="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" aria-hidden="true" />
        </CollapsibleTrigger>
        <CollapsibleContent className="flex min-w-0 flex-col gap-1 px-4 pb-3">
          <pre className="text-xs whitespace-pre-wrap break-all">{JSON.stringify(call.args)}</pre>
          {call.content !== undefined && (
            <pre className="text-xs whitespace-pre-wrap break-all max-h-40 overflow-y-auto">{call.content}</pre>
          )}
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}
