import { useQuery } from '@tanstack/react-query'
import { threadQueries } from '../queries/threads'

interface Props {
  activeId: string
  open: boolean
  /** A running answer must not be cut by a switch, so the list waits for it. */
  busy: boolean
  onSelect: (threadId: string) => void
  onNew: () => void
  onClose: () => void
}

/** The Conversations, newest first. Beside the chat on wide screens, over it on narrow ones. */
export function Sidebar({ activeId, open, busy, onSelect, onNew, onClose }: Props) {
  const { data, error, isPending, refetch } = useQuery(threadQueries.list())
  return (
    <aside
      aria-label="Conversations"
      className={`${open ? 'flex' : 'hidden'} flex-col fixed inset-0 z-30 bg-base-100 lg:flex lg:static lg:inset-auto lg:w-72 lg:shrink-0 lg:border-r lg:border-base-300`}
    >
      <div className="flex items-center justify-between gap-2 p-4 border-b border-base-300">
        <h2 className="font-bold">Conversations</h2>
        <div className="flex gap-2">
          <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={onNew}>
            New Conversation
          </button>
          <button type="button" className="btn btn-sm lg:hidden" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {isPending && <span className="loading loading-spinner m-2" />}
        {error && (
          <div role="alert" className="alert alert-error alert-soft flex-col items-start">
            <span>The Conversations could not be loaded.</span>
            <button type="button" className="btn btn-sm" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        )}
        {data?.length === 0 && <p className="text-sm opacity-60 p-2">No Conversations yet. Ask a question to start one.</p>}
        {data && data.length > 0 && (
          <ul className="menu w-full">
            {data.map((thread) => (
              <li key={thread.thread_id}>
                <button
                  type="button"
                  className={thread.thread_id === activeId ? 'menu-active' : ''}
                  aria-current={thread.thread_id === activeId ? 'true' : undefined}
                  disabled={busy && thread.thread_id !== activeId}
                  onClick={() => onSelect(thread.thread_id)}
                >
                  <span className="truncate">{thread.title || 'Untitled Conversation'}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
