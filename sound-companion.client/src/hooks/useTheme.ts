import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dark'

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  return () => observer.disconnect()
}

/** The theme in force, read from the `.dark` class that the script in `index.html` and `ThemeToggle` keep up to date. */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, () => (document.documentElement.classList.contains('dark') ? 'dark' : 'light'))
}
