import { useMemo, useState, type CSSProperties } from 'react'
import { Outlet } from 'react-router'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'
import { ChatActivityContext } from '../state/chatActivity'
import { AppSidebar } from './AppSidebar'
import { SIDEBAR_DEFAULT, SIDEBAR_MAX, SIDEBAR_MIN, SidebarResizeHandle } from './SidebarResizeHandle'

const WIDTH_KEY = 'sidebar-width'

function storedWidth(): number {
  try {
    const value = Number(localStorage.getItem(WIDTH_KEY))
    if (value >= SIDEBAR_MIN && value <= SIDEBAR_MAX) return value
  } catch {
    // blocked storage: the default applies
  }
  return SIDEBAR_DEFAULT
}

/** The frame of every page: the shadcn sidebar (pages and Conversations, resizable) beside the page. */
export function AppShell() {
  const [streaming, setStreaming] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const activity = useMemo(() => ({ streaming, setStreaming, inspectorOpen, setInspectorOpen }), [streaming, inspectorOpen])
  const [width, setWidth] = useState(storedWidth)
  const [dragging, setDragging] = useState(false)

  function resize(next: number) {
    setWidth(next)
    try {
      localStorage.setItem(WIDTH_KEY, String(next))
    } catch {
      // the width just lasts until the page is closed
    }
  }

  return (
    <ChatActivityContext value={activity}>
      <SidebarProvider
        className={cn('h-svh min-h-0', dragging && 'select-none **:data-[slot=sidebar-container]:transition-none **:data-[slot=sidebar-gap]:transition-none')}
        style={{ '--sidebar-width': `${width}px` } as CSSProperties}
      >
        <AppSidebar handle={<SidebarResizeHandle width={width} onResize={resize} onDraggingChange={setDragging} />} />
        <SidebarInset className="min-h-0 min-w-0 overflow-y-auto">
          <Outlet />
        </SidebarInset>
      </SidebarProvider>
    </ChatActivityContext>
  )
}
