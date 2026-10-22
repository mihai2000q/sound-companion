import { useEffect } from 'react'
import { labelOf } from '../lib/citations'
import type { ChatMessage } from '../types/chat'

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
    if (open && focus) document.getElementById(`chunk-${focus.chunkId}`)?.scrollIntoView({ block: 'center' })
  }, [open, focus])

  const citations = message?.citations ?? []
  const queries = message?.queries ?? []
  return (
    <aside
      aria-label="Inspector"
      className={`${open ? 'flex' : 'hidden'} flex-col fixed inset-0 z-20 bg-base-100 lg:static lg:inset-auto lg:w-96 lg:border-l lg:border-base-300`}
    >
      <div className="flex items-center justify-between p-4 border-b border-base-300">
        <h2 className="font-bold">Inspector</h2>
        <button type="button" className="btn btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {!message || (citations.length === 0 && queries.length === 0) ? (
          <p className="text-sm opacity-60">Ask something that needs a search to see the queries and the chunks here.</p>
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
                <article
                  key={chunk.id}
                  id={`chunk-${chunk.id}`}
                  className={`card card-border card-sm bg-base-100 ${focus?.chunkId === chunk.id ? 'border-primary ring-2 ring-primary' : ''}`}
                >
                  <div className="card-body">
                    <div className="flex items-start justify-between gap-2">
                      <a className="link text-sm font-medium" href={chunk.url} target="_blank" rel="noreferrer">
                        {labelOf(chunk)}
                      </a>
                      <span className="badge badge-sm badge-soft">{chunk.score.toFixed(3)}</span>
                    </div>
                    <p className="text-xs whitespace-pre-wrap max-h-40 overflow-y-auto">{chunk.content}</p>
                  </div>
                </article>
              ))}
            </section>
          </>
        )}
      </div>
    </aside>
  )
}
