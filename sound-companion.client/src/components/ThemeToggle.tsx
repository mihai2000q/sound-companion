import { useState } from 'react'

type Theme = 'light' | 'dark'

/** The stored choice is applied by a script in `index.html`; without one the OS preference decides (DaisyUI `--prefersdark`, and the script sets `.dark`). */
function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme
  if (set === 'light' || set === 'dark') return set
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** A DaisyUI `swap` between a sun and a moon; the choice is kept in `localStorage` when it is available. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme)

  function toggle(dark: boolean) {
    const next: Theme = dark ? 'dark' : 'light'
    document.documentElement.dataset.theme = next
    document.documentElement.classList.toggle('dark', next === 'dark')
    setTheme(next)
    try {
      localStorage.setItem('theme', next)
    } catch {
      // private window or blocked storage: the choice just lasts until the page is closed
    }
  }

  return (
    <label className="btn btn-sm btn-ghost btn-square swap swap-rotate" title="Switch theme">
      <input type="checkbox" aria-label="Dark theme" checked={theme === 'dark'} onChange={(event) => toggle(event.target.checked)} />
      <svg className="swap-off size-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 18a6 6 0 1 1 0-12 6 6 0 0 1 0 12Zm0-2a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM11 1h2v3h-2V1Zm0 19h2v3h-2v-3ZM3.5 5l1.4-1.4 2.1 2.1L5.6 7.1 3.5 5Zm13.5 13.5 1.4-1.4 2.1 2.1-1.4 1.4-2.1-2.1ZM1 11h3v2H1v-2Zm19 0h3v2h-3v-2ZM5 20.5l-1.4-1.4 2.1-2.1 1.4 1.4L5 20.5ZM18.5 7l-1.4-1.4 2.1-2.1L20.6 5 18.5 7Z" />
      </svg>
      <svg className="swap-on size-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
      </svg>
    </label>
  )
}
