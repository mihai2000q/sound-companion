import { useMemo, useState } from 'react'
import { Outlet } from 'react-router'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { ChatActivityContext } from '../state/chatActivity'
import { AppSidebar } from './AppSidebar'

/** The frame of every page: the shadcn sidebar (pages and Conversations) beside the page. */
export function AppShell() {
  const [streaming, setStreaming] = useState(false)
  const activity = useMemo(() => ({ streaming, setStreaming }), [streaming])
  return (
    <ChatActivityContext value={activity}>
      <SidebarProvider className="h-svh min-h-0">
        <AppSidebar />
        <SidebarInset className="min-h-0 min-w-0 overflow-y-auto">
          <Outlet />
        </SidebarInset>
      </SidebarProvider>
    </ChatActivityContext>
  )
}
