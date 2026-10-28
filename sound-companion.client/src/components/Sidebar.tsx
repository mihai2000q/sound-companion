import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteThread, exportThread, threadKeys, threadQueries } from '../queries/threads'
import type { ThreadSummary } from '../types/threads'
import { ContextMenu } from './ContextMenu'

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
  const queryClient = useQueryClient()
  const [asking, setAsking] = useState<ThreadSummary | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const [menu, setMenu] = useState<{ thread: ThreadSummary; x: number; y: number; opener: HTMLElement } | null>(null)

  const remove = useMutation({
    mutationFn: (thread: ThreadSummary) => deleteThread(thread.thread_id),
    onSuccess: async (_, thread) => {
      setAsking(null)
      await queryClient.invalidateQueries({ queryKey: threadKeys.list() })
      if (thread.thread_id === activeId) onNew() // the open one is gone: an empty new Conversation
    },
    onError: () => {
      setAsking(null)
      setFailure('The Conversation could not be deleted.')
    },
  })
  const download = useMutation({
    mutationFn: exportThread,
    onError: () => setFailure('The Conversation could not be exported.'),
  })
  const closeMenu = useCallback(() => setMenu(null), [])
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
        {failure && (
          <div role="alert" className="alert alert-error alert-soft mb-2 flex justify-between">
            <span>{failure}</span>
            <button type="button" className="btn btn-xs" onClick={() => setFailure(null)}>
              Dismiss
            </button>
          </div>
        )}
        {data?.length === 0 && <p className="text-sm opacity-60 p-2">No Conversations yet. Ask a question to start one.</p>}
        {data && data.length > 0 && (
          <ul className="menu w-full">
            {data.map((thread) => (
              <li key={thread.thread_id} className="group flex-row items-center">
                <button
                  type="button"
                  className={`flex-1 min-w-0 ${thread.thread_id === activeId ? 'menu-active' : ''}`}
                  aria-current={thread.thread_id === activeId ? 'true' : undefined}
                  aria-haspopup="menu"
                  disabled={busy && thread.thread_id !== activeId}
                  onClick={() => onSelect(thread.thread_id)}
                  onContextMenu={(event) => {
                    event.preventDefault()
                    setMenu({ thread, x: event.clientX, y: event.clientY, opener: event.currentTarget })
                  }}
                >
                  <span className="truncate">{thread.title || 'Untitled Conversation'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-xs btn-square lg:opacity-0 lg:group-hover:opacity-100 focus-visible:opacity-100"
                  aria-label={`Actions for ${thread.title || 'Untitled Conversation'}`}
                  aria-haspopup="menu"
                  aria-expanded={menu?.thread.thread_id === thread.thread_id}
                  onClick={(event) => {
                    const box = event.currentTarget.getBoundingClientRect()
                    setMenu({ thread, x: box.left, y: box.bottom + 4, opener: event.currentTarget })
                  }}
                >
                  <svg className="size-4 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M5 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm7 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm7 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          opener={menu.opener}
          onClose={closeMenu}
          items={[
            {
              label: 'Export',
              disabled: download.isPending,
              onSelect: () => {
                setFailure(null)
                download.mutate(menu.thread)
              },
            },
            {
              label: 'Delete',
              danger: true,
              disabled: busy && menu.thread.thread_id === activeId,
              onSelect: () => {
                setFailure(null)
                setAsking(menu.thread)
              },
            },
          ]}
        />
      )}
      {asking && (
        <DeleteDialog
          thread={asking}
          deleting={remove.isPending}
          onConfirm={() => remove.mutate(asking)}
          onCancel={() => setAsking(null)}
        />
      )}
    </aside>
  )
}

/** A DaisyUI modal on a native `<dialog>`: focus stays inside it and Escape cancels. */
function DeleteDialog({ thread, deleting, onConfirm, onCancel }: { thread: ThreadSummary; deleting: boolean; onConfirm: () => void; onCancel: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => dialog.current?.showModal(), [])
  return (
    <dialog ref={dialog} className="modal" onClose={onCancel}>
      <div className="modal-box">
        <h3 className="font-bold text-lg">Delete this Conversation?</h3>
        <p className="py-4 break-words">
          “{thread.title || 'Untitled Conversation'}” and its messages will be removed. This cannot be undone.
        </p>
        <div className="modal-action">
          <button type="button" className="btn" disabled={deleting} onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="btn btn-error" disabled={deleting} onClick={onConfirm}>
            {deleting && <span className="loading loading-spinner loading-xs" />}
            Delete
          </button>
        </div>
      </div>
    </dialog>
  )
}
