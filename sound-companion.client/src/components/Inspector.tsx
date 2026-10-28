import { useEffect } from 'react'
import { labelOf } from '../lib/citations'
import type { ChatMessage } from '../types/chat'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

export interface ChunkFocus {
  messageId: string
  chunkId: string
}

interface Props {
  message: ChatMessage | undefined
  open: boolean
  focus: ChunkFocus | null
  onClose: () => void
}

/** The RAG process of one answer: the queries and every retrieved chunk. Beside the chat on wide screens, over it on narrow ones. */
export function Inspector({ message, open, focus, onClose }: Props) {
  // a new object per chip click, so clicking the same chip again scrolls again
  useEffect(() => {
    // a frame later: in a sheet the chunks are mounted after the open state changes
    if (open && focus) requestAnimationFrame(() => document.getElementById(`chunk-${focus.chunkId}`)?.scrollIntoView({ block: 'center' }))
  }, [open, focus])

  const citations = message?.citations ?? []
  const queries = message?.queries ?? []
  const desktop = useMediaQuery('(min-width: 1024px)')
  const body = (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-4 p-4">
        {!message || (citations.length === 0 && queries.length === 0) ? (
          <p className="text-sm text-muted-foreground">Ask something that needs a search to see the queries and the chunks here.</p>
        ) : (
          <>
            <section>
              <h3 className="text-sm font-semibold mb-1">Queries</h3>
              <ul className="list-disc pl-5 text-sm">
                {queries.map((query, i) => (
                  <li key={i}>{query}</li>
                ))}
              </ul>
            </section>
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">Retrieved chunks ({citations.length})</h3>
              {citations.map((chunk) => (
                <Card
                  key={chunk.id}
                  id={`chunk-${chunk.id}`}
                  className={`gap-0 py-0 shadow-none ${focus?.chunkId === chunk.id ? 'border-primary ring-2 ring-primary' : ''}`}
                >
                  <CardContent className="flex flex-col gap-2 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <a className="text-sm hover:underline font-medium break-words min-w-0" href={chunk.url} target="_blank" rel="noreferrer">
                        {labelOf(chunk)}
                      </a>
                      <Badge variant="secondary" className="shrink-0" title="Retrieval score">
                        {chunk.score.toFixed(3)}
                      </Badge>
                    </div>
                    <p className="text-xs whitespace-pre-wrap max-h-40 overflow-y-auto">{chunk.content}</p>
                    <Badge variant="outline" className="self-start">
                      {chunk.license}
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </section>
          </>
        )}
      </div>
    </ScrollArea>
  )

  // docked beside the chat on wide screens, a sheet over it on narrow ones
  if (desktop)
    return (
      <aside aria-label="Inspector" className={`${open ? 'flex' : 'hidden'} w-96 flex-col border-l bg-background`}>
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="font-bold">Inspector</h2>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
        {body}
      </aside>
    )
  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="right" aria-label="Inspector" className="w-full gap-0 sm:max-w-md">
        <div className="border-b p-4">
          <SheetTitle>Inspector</SheetTitle>
          <SheetDescription className="sr-only">The queries and retrieved chunks of an answer</SheetDescription>
        </div>
        {body}
      </SheetContent>
    </Sheet>
  )
}
