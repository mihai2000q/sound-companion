import { Fragment, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ellipsis } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger } from '@/components/ui/context-menu'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { groupThreads } from '../lib/threadGroups'
import { deleteThread, exportThread, renameThread, threadKeys, threadQueries } from '../queries/threads'
import type { ThreadSummary } from '../types/threads'
import { Spinner } from './Spinner'

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
  const [filter, setFilter] = useState('')
  const [renaming, setRenaming] = useState<string | null>(null)
  const keepFocus = useRef(false) // a menu gives the focus back to its opener, which would take it from the rename field

  const remove = useMutation({
    mutationFn: (thread: ThreadSummary) => deleteThread(thread.thread_id),
    onSuccess: async (_, thread) => {
      setAsking(null)
      await queryClient.invalidateQueries({ queryKey: threadKeys.list() })
      if (thread.thread_id === activeId) onNew() // the open one is gone: an empty new Conversation
    },
    onError: () => {
      setAsking(null)
      toast.error('The Conversation could not be deleted.')
    },
  })
  const rename = useMutation({
    mutationFn: ({ thread, title }: { thread: ThreadSummary; title: string }) => renameThread(thread.thread_id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.list() }),
    onError: () => toast.error('The Conversation could not be renamed.'),
  })
  const download = useMutation({
    mutationFn: exportThread,
    onError: () => toast.error('The Conversation could not be exported.'),
  })
  const needle = filter.trim().toLowerCase()
  const shown = data?.filter((thread) => (thread.title || 'Untitled Conversation').toLowerCase().includes(needle))
  const desktop = useMediaQuery('(min-width: 1024px)')

  /** The same three actions in the right-click menu and in the "⋯" menu. */
  function actions(thread: ThreadSummary, Item: typeof ContextMenuItem | typeof DropdownMenuItem) {
    return (
      <>
        <Item disabled={download.isPending} onSelect={() => download.mutate(thread)}>
          Export
        </Item>
        <Item
          onSelect={() => {
            keepFocus.current = true
            setRenaming(thread.thread_id)
          }}
        >
          Rename
        </Item>
        <Item variant="destructive" disabled={busy && thread.thread_id === activeId} onSelect={() => setAsking(thread)}>
          Delete
        </Item>
      </>
    )
  }
  const onCloseAutoFocus = (event: Event) => {
    if (!keepFocus.current) return
    keepFocus.current = false
    event.preventDefault()
  }

  const content = (
    <>
      <div className="flex items-center justify-between gap-2 border-b p-4">
        {desktop ? <h2 className="font-bold">Conversations</h2> : <SheetTitle>Conversations</SheetTitle>}
        <Button type="button" size="sm" disabled={busy} onClick={onNew}>
          New Conversation
        </Button>
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
          {data?.length === 0 && <p className="p-2 text-sm text-muted-foreground">No Conversations yet. Ask a question to start one.</p>}
          {shown && data && data.length > 0 && shown.length === 0 && (
            <p className="p-2 text-sm text-muted-foreground">No Conversation matches “{filter.trim()}”.</p>
          )}
          {shown && shown.length > 0 && (
            <ul className="flex w-full flex-col gap-0.5">
              {groupThreads(shown).map((group) => (
                <Fragment key={group.label}>
                  <li className="px-3 pt-3 pb-1 text-xs font-semibold text-muted-foreground">{group.label}</li>
                  {group.threads.map((thread) => {
                    const active = thread.thread_id === activeId
                    const title = thread.title || 'Untitled Conversation'
                    return renaming === thread.thread_id ? (
                      <li key={thread.thread_id}>
                        <RenameField
                          initial={thread.title || ''}
                          onSave={(next) => {
                            setRenaming(null)
                            rename.mutate({ thread, title: next })
                          }}
                          onCancel={() => setRenaming(null)}
                        />
                      </li>
                    ) : (
                      <li key={thread.thread_id}>
                        <ContextMenu>
                          <ContextMenuTrigger asChild>
                            <div className={cn('group flex items-center rounded-md select-none hover:bg-accent', active && 'bg-accent font-medium')}>
                              <button
                                type="button"
                                className="min-w-0 flex-1 rounded-md px-3 py-1.5 text-left text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
                                aria-current={active ? 'true' : undefined}
                                disabled={busy && !active}
                                onClick={() => onSelect(thread.thread_id)}
                              >
                                <span className="block truncate">{title}</span>
                              </button>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-xs"
                                    className="mr-1 focus-visible:opacity-100 data-[state=open]:opacity-100 lg:opacity-0 lg:group-hover:opacity-100"
                                    aria-label={`Actions for ${title}`}
                                  >
                                    <Ellipsis />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="start" className="w-44" onCloseAutoFocus={onCloseAutoFocus}>
                                  {actions(thread, DropdownMenuItem)}
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </ContextMenuTrigger>
                          <ContextMenuContent className="w-44" onCloseAutoFocus={onCloseAutoFocus}>
                            {actions(thread, ContextMenuItem)}
                          </ContextMenuContent>
                        </ContextMenu>
                      </li>
                    )
                  })}
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
      <DeleteDialog
        thread={asking}
        deleting={remove.isPending}
        onConfirm={() => asking && remove.mutate(asking)}
        onCancel={() => setAsking(null)}
      />
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

/** An `alert-dialog` for the delete: focus stays inside it and Escape cancels, unless the request is running. */
function DeleteDialog({ thread, deleting, onConfirm, onCancel }: { thread: ThreadSummary | null; deleting: boolean; onConfirm: () => void; onCancel: () => void }) {
  return (
    <AlertDialog open={thread !== null} onOpenChange={(next) => !next && !deleting && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this Conversation?</AlertDialogTitle>
          <AlertDialogDescription className="break-words">
            “{thread?.title || 'Untitled Conversation'}” and its messages will be removed. This cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
          <Button type="button" variant="destructive" disabled={deleting} onClick={onConfirm}>
            {deleting && <Spinner />}
            Delete
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
