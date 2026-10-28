import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { groupThreads } from '../lib/threadGroups'
import { deleteThread, exportThread, renameThread, threadKeys, threadQueries } from '../queries/threads'
import type { ThreadSummary } from '../types/threads'
import { ContextMenu } from './ContextMenu'
import { Ellipsis } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { Spinner } from './Spinner'

const TOAST_MS = 5000
const MAX_TITLE_LENGTH = 100 // the server refuses a longer one

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
  const [filter, setFilter] = useState('')
  const [renaming, setRenaming] = useState<string | null>(null)
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
  const rename = useMutation({
    mutationFn: ({ thread, title }: { thread: ThreadSummary; title: string }) => renameThread(thread.thread_id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.list() }),
    onError: () => setFailure('The Conversation could not be renamed.'),
  })
  const download = useMutation({
    mutationFn: exportThread,
    onError: () => setFailure('The Conversation could not be exported.'),
  })
  const needle = filter.trim().toLowerCase()
  const shown = data?.filter((thread) => (thread.title || 'Untitled Conversation').toLowerCase().includes(needle))
  // a toast goes away by itself; a new failure restarts the timer
  useEffect(() => {
    if (!failure) return
    const timer = setTimeout(() => setFailure(null), TOAST_MS)
    return () => clearTimeout(timer)
  }, [failure])
  const closeMenu = useCallback(() => setMenu(null), [])
  const desktop = useMediaQuery('(min-width: 1024px)')
  const content = (
    <>
      <div className="flex items-center justify-between gap-2 p-4 border-b">
        {desktop ? <h2 className="font-bold">Conversations</h2> : <SheetTitle>Conversations</SheetTitle>}
        <div className="flex gap-2">
          <Button type="button" size="sm" disabled={busy} onClick={onNew}>
            New Conversation
          </Button>
        </div>
      </div>
      {data && data.length > 0 && (
        <div className="p-2 pb-0">
          <Input
            type="search"
            className="h-8"
            placeholder="Search Conversations"
            aria-label="Search Conversations"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
      )}
      <ScrollArea className="min-h-0 flex-1">
        <div className="p-2">
        {isPending && (
          <div className="flex flex-col gap-2 p-2" aria-label="Loading Conversations" role="status">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        )}
        {error && (
          <Alert variant="destructive" className="flex flex-col items-start gap-2">
            <span>The Conversations could not be loaded.</span>
            <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          </Alert>
        )}
        {data?.length === 0 && <p className="text-sm opacity-60 p-2">No Conversations yet. Ask a question to start one.</p>}
        {shown && data && data.length > 0 && shown.length === 0 && <p className="text-sm opacity-60 p-2">No Conversation matches “{filter.trim()}”.</p>}
        {shown && shown.length > 0 && (
          <ul className="menu w-full">
            {groupThreads(shown).map((group) => (
              <Fragment key={group.label}>
                <li className="menu-title">{group.label}</li>
                {group.threads.map((thread) => (
                  renaming === thread.thread_id ? (
                    <li key={thread.thread_id}>
                      <RenameField
                        initial={thread.title || ''}
                        onSave={(title) => {
                          setRenaming(null)
                          rename.mutate({ thread, title })
                        }}
                        onCancel={() => setRenaming(null)}
                      />
                    </li>
                  ) : (
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
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="lg:opacity-0 lg:group-hover:opacity-100 focus-visible:opacity-100"
                        aria-label={`Actions for ${thread.title || 'Untitled Conversation'}`}
                        aria-haspopup="menu"
                        aria-expanded={menu?.thread.thread_id === thread.thread_id}
                        onClick={(event) => {
                          const box = event.currentTarget.getBoundingClientRect()
                          setMenu({ thread, x: box.left, y: box.bottom + 4, opener: event.currentTarget })
                        }}
                      >
                        <Ellipsis />
                      </Button>
                    </li>
                  )
                ))}
              </Fragment>
            ))}
          </ul>
        )}
        </div>
      </ScrollArea>
    </>
  )
  return (
    <>
      {desktop ? (
        <aside aria-label="Conversations" className="flex w-72 shrink-0 flex-col border-r bg-background">
          {content}
        </aside>
      ) : (
        <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
          <SheetContent side="left" aria-label="Conversations" className="w-full gap-0 sm:max-w-sm">
            <SheetDescription className="sr-only">Your Conversations, newest first</SheetDescription>
            {content}
          </SheetContent>
        </Sheet>
      )}
      {failure && (
        <div className="toast toast-end toast-bottom z-50">
          <div role="alert" className="alert alert-error">
            <span>{failure}</span>
            <Button type="button" variant="ghost" size="xs" onClick={() => setFailure(null)}>
              Dismiss
            </Button>
          </div>
        </div>
      )}
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
              label: 'Rename',
              onSelect: () => setRenaming(menu.thread.thread_id),
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
    </>
  )
}

/** The title of a row as a text field: Enter and a click away save, Escape cancels. A title that is empty or unchanged is not sent. */
function RenameField({ initial, onSave, onCancel }: { initial: string; onSave: (title: string) => void; onCancel: () => void }) {
  const finished = useRef(false) // Escape unmounts the field, which can still fire a blur
  const finish = (title: string | null) => {
    if (finished.current) return
    finished.current = true
    if (title === null || title.trim() === '' || title.trim() === initial) onCancel()
    else onSave(title.trim())
  }
  return (
    <Input
      type="text"
      className="h-8"
      aria-label="Conversation title"
      defaultValue={initial}
      maxLength={MAX_TITLE_LENGTH}
      autoFocus
      onFocus={(event) => event.currentTarget.select()}
      onBlur={(event) => finish(event.currentTarget.value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') finish(event.currentTarget.value)
        else if (event.key === 'Escape') finish(null)
      }}
    />
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
          <Button type="button" variant="outline" disabled={deleting} onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" disabled={deleting} onClick={onConfirm}>
            {deleting && <Spinner />}
            Delete
          </Button>
        </div>
      </div>
    </dialog>
  )
}