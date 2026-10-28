import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { ThemeToggle } from './ThemeToggle'
import { Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'

const PAGES = [
  { to: '/', label: 'Chat' },
  { to: '/monitoring', label: 'Monitoring' },
  { to: '/health', label: 'Health' },
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
    <header className="navbar flex-wrap gap-y-1 bg-base-100 border-b border-base-300 px-2 sm:px-4">
      <div className="navbar-start w-auto flex-1 gap-1">
        {onOpenSidebar && (
          <Button type="button" variant="ghost" size="icon-sm" className="lg:hidden" aria-label="Open Conversations" onClick={onOpenSidebar}>
            <Menu className="size-5" />
          </Button>
        )}
        <Link to="/" className="text-lg font-bold px-2 truncate">
          Sound Companion
        </Link>
        <nav aria-label="Pages" className="max-md:hidden">
          <ul className="menu menu-horizontal menu-sm gap-1">
            {PAGES.map((page) => (
              <li key={page.to}>
                <NavLink to={page.to} end className={({ isActive }) => (isActive ? 'menu-active' : '')}>
                  {page.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <div className="navbar-end w-auto flex-wrap gap-2">
        {children}
        <div className="dropdown dropdown-end md:hidden">
          <Button type="button" variant="ghost" size="sm" tabIndex={0}>
            Pages
          </Button>
          <ul tabIndex={0} className="menu menu-sm dropdown-content bg-base-100 rounded-box z-40 mt-2 w-40 p-2 shadow">
            {PAGES.map((page) => (
              <li key={page.to}>
                <NavLink to={page.to} end className={({ isActive }) => (isActive ? 'menu-active' : '')}>
                  {page.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}
