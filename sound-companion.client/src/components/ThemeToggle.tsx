import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useTheme } from '../hooks/useTheme'

/** Switches the `.dark` class; the choice is kept in `localStorage` when it is available. The script in `index.html` applies it on load. */
export function ThemeToggle() {
  const theme = useTheme()

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    try {
      localStorage.setItem('theme', next)
    } catch {
      // private window or blocked storage: the choice just lasts until the page is closed
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button type="button" variant="ghost" size="icon-sm" aria-label="Dark theme" aria-pressed={theme === 'dark'} onClick={toggle}>
          {theme === 'dark' ? <Moon className="size-5" /> : <Sun className="size-5" />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>Switch theme</TooltipContent>
    </Tooltip>
  )
}
