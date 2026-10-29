import type { ReactNode } from 'react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { ThemeToggle } from './ThemeToggle'

interface Props {
  /** Page-specific controls, shown before the theme toggle. */
  children?: ReactNode
}

/** The top bar of every page: the sidebar toggle, page-specific controls and the theme toggle. */
export function AppBar({ children }: Props) {
  return (
    <header className="flex shrink-0 flex-wrap items-center gap-2 border-b bg-background px-2 py-2 sm:px-4">
      <SidebarTrigger />
      <div className="ml-auto flex flex-wrap items-center gap-2">
        {children}
        <ThemeToggle />
      </div>
    </header>
  )
}
