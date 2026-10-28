import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { ThemeToggle } from './ThemeToggle'

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
          <button type="button" className="btn btn-ghost btn-square btn-sm lg:hidden" aria-label="Open Conversations" onClick={onOpenSidebar}>
            <svg className="size-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 5h18v2H3V5Zm0 6h18v2H3v-2Zm0 6h18v2H3v-2Z" />
            </svg>
          </button>
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
          <button type="button" tabIndex={0} className="btn btn-sm btn-ghost">
            Pages
          </button>
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
