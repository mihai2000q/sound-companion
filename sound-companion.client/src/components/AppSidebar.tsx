import { Fragment, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, Ellipsis, MessageSquare, Music2, SquarePen, type LucideIcon } from 'lucide-react'
import { Link, NavLink, useLocation, useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger } from '@/components/ui/context-menu'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  useSidebar,
} from '@/components/ui/sidebar'
import { groupThreads } from '../lib/threadGroups'
import { deleteThread, exportThread, renameThread, threadKeys, threadQueries } from '../queries/threads'
import { useChatActivity } from '../state/chatActivity'
import type { ThreadSummary } from '../types/threads'
import { Spinner } from './Spinner'

const MAX_TITLE_LENGTH = 100 // the server refuses a longer one

const PAGES: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/', label: 'Chat', icon: MessageSquare },
  { to: '/monitoring', label: 'Monitoring', icon: Activity },
]

/** Pages and Conversations, newest first, in the shadcn sidebar of every page. */
export function AppSidebar() {
  const { data, error, isPending, refetch } = useQuery(threadQueries.list())
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const { streaming: busy } = useChatActivity()
  const { isMobile, setOpenMobile } = useSidebar()
  const activeId = pathname === '/' ? params.get('c') : null
  const [asking, setAsking] = useState<ThreadSummary | null>(null)
  const [filter, setFilter] = useState('')
  const [renaming, setRenaming] = useState<string | null>(null)
  const keepFocus = useRef(false) // a menu gives the focus back to its opener, which would take it from the rename field

  /** Opens a Conversation in the chat (the `c` parameter of the URL) and closes the sidebar when it is a sheet. */
  function select(threadId: string) {
    navigate({ pathname: '/', search: `?c=${threadId}` })
    if (isMobile) setOpenMobile(false)
  }
  const startNew = () => select(crypto.randomUUID())

  const remove = useMutation({
    mutationFn: (thread: ThreadSummary) => deleteThread(thread.thread_id),
    onSuccess: async (_, thread) => {
      setAsking(null)
      await queryClient.invalidateQueries({ queryKey: threadKeys.list() })
      if (thread.thread_id === activeId) startNew() // the open one is gone: an empty new Conversation
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

  return (
    <>
      <Sidebar aria-label="Conversations">
        <SidebarHeader className="gap-5 px-5 pt-5 pb-4">
          <Link to="/" className="flex items-center gap-2 font-serif text-xl font-medium tracking-tight">
            <span className="grid size-7 place-items-center rounded-full bg-brass text-brass-foreground" aria-hidden="true">
              <Music2 className="size-4" />
            </span>
            Sound Companion
          </Link>
          <nav aria-label="Pages">
            <SidebarMenu className="gap-2">
              <SidebarMenuItem>
                <SidebarMenuButton className="h-9 px-3" disabled={busy} onClick={startNew}>
                  <SquarePen />
                  New Conversation
                </SidebarMenuButton>
              </SidebarMenuItem>
              {PAGES.map((page) => (
                <SidebarMenuItem key={page.to}>
                  <SidebarMenuButton asChild isActive={pathname === page.to} className="h-9 px-3">
                    <NavLink to={page.to} end onClick={() => isMobile && setOpenMobile(false)}>
                      <page.icon />
                      {page.label}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </nav>
          {data && data.length > 0 && (
            <Input
              type="search"
              className="h-8"
              placeholder="Search Conversations"
              aria-label="Search Conversations"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          )}
        </SidebarHeader>
        <SidebarContent className="gap-2 px-3 pb-4">
          {isPending && (
            <SidebarGroup aria-label="Loading Conversations" role="status">
              <SidebarMenu>
                {[0, 1, 2, 3, 4].map((i) => (
                  <SidebarMenuItem key={i}>
                    <SidebarMenuSkeleton />
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroup>
          )}
          {error && (
            <SidebarGroup>
              <Alert variant="destructive" className="flex flex-col items-start gap-2">
                <span>The Conversations could not be loaded.</span>
                <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
              </Alert>
            </SidebarGroup>
          )}
          {data?.length === 0 && <p className="p-4 text-sm text-muted-foreground">No Conversations yet. Ask a question to start one.</p>}
          {shown && data && data.length > 0 && shown.length === 0 && (
            <p className="p-4 text-sm text-muted-foreground">No Conversation matches “{filter.trim()}”.</p>
          )}
          {shown &&
            groupThreads(shown).map((group) => (
              <SidebarGroup key={group.label}>
                <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu className="gap-1">
                    {group.threads.map((thread) => {
                      const active = thread.thread_id === activeId
                      const title = thread.title || 'Untitled Conversation'
                      return (
                        <Fragment key={thread.thread_id}>
                          {renaming === thread.thread_id ? (
                            <SidebarMenuItem>
                              <RenameField
                                initial={thread.title || ''}
                                onSave={(next) => {
                                  setRenaming(null)
                                  rename.mutate({ thread, title: next })
                                }}
                                onCancel={() => setRenaming(null)}
                              />
                            </SidebarMenuItem>
                          ) : (
                            <ContextMenu>
                              <ContextMenuTrigger asChild>
                                <SidebarMenuItem className="select-none">
                                  <SidebarMenuButton
                                    isActive={active}
                                    className="h-9 px-3"
                                    aria-current={active ? 'true' : undefined}
                                    disabled={busy && !active}
                                    onClick={() => select(thread.thread_id)}
                                  >
                                    <span className="truncate">{title}</span>
                                  </SidebarMenuButton>
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <SidebarMenuAction showOnHover aria-label={`Actions for ${title}`}>
                                        <Ellipsis />
                                      </SidebarMenuAction>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="start" className="w-44" onCloseAutoFocus={onCloseAutoFocus}>
                                      {actions(thread, DropdownMenuItem)}
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </SidebarMenuItem>
                              </ContextMenuTrigger>
                              <ContextMenuContent className="w-44" onCloseAutoFocus={onCloseAutoFocus}>
                                {actions(thread, ContextMenuItem)}
                              </ContextMenuContent>
                            </ContextMenu>
                          )}
                        </Fragment>
                      )
                    })}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            ))}
        </SidebarContent>
      </Sidebar>
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
