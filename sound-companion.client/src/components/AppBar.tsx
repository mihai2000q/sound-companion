import type { ReactNode } from 'react'
import { Menu, Music2 } from 'lucide-react'
import { Link, NavLink } from 'react-router'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { ThemeToggle } from './ThemeToggle'

const PAGES = [
  { to: '/', label: 'Chat' },
  { to: '/monitoring', label: 'Monitoring' },
]

interface Props {
  /** Only the chat has a Conversations sidebar to open. */
  onOpenSidebar?: () => void
  /** Page-specific controls, shown before the theme toggle. */
  children?: ReactNode
}

/** The top bar of every page: brand, the pages, page-specific controls and the theme toggle. */
export function AppBar({ onOpenSidebar, children }: Props) {
  return (
    <header className="flex flex-wrap items-center gap-y-1 border-b bg-background px-2 py-2 sm:px-4">
      <div className="flex flex-1 items-center gap-1">
        {onOpenSidebar && (
          <Button type="button" variant="ghost" size="icon-sm" className="lg:hidden" aria-label="Open Conversations" onClick={onOpenSidebar}>
            <Menu className="size-5" />
          </Button>
        )}
        <Link to="/" className="flex items-center gap-2 truncate px-2 font-serif text-xl font-medium tracking-tight">
          <span className="grid size-7 place-items-center rounded-full bg-brass text-brass-foreground" aria-hidden="true">
            <Music2 className="size-4" />
          </span>
          Sound Companion
        </Link>
        <nav aria-label="Pages" className="flex gap-1 max-md:hidden">
          {PAGES.map((page) => (
            <NavLink
              key={page.to}
              to={page.to}
              end
              className={({ isActive }) =>
                cn('rounded-md px-3 py-1 text-sm hover:bg-accent', isActive && 'bg-accent font-medium text-accent-foreground')
              }
            >
              {page.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {children}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="ghost" size="sm" className="md:hidden">
              Pages
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            {PAGES.map((page) => (
              <DropdownMenuItem key={page.to} asChild>
                <NavLink to={page.to} end className={({ isActive }) => (isActive ? 'bg-accent font-medium' : '')}>
                  {page.label}
                </NavLink>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <ThemeToggle />
      </div>
    </header>
  )
}
