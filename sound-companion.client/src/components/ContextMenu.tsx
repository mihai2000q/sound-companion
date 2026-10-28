import { useEffect, useLayoutEffect, useRef, type KeyboardEvent } from 'react'

export interface ContextMenuItem {
  label: string
  danger?: boolean
  disabled?: boolean
  onSelect: () => void
}

interface Props {
  /** Where the menu opens, in viewport pixels (the pointer, or the corner of the button that opened it). */
  x: number
  y: number
  items: ContextMenuItem[]
  /** The element that opened the menu; it gets the focus back when the menu closes. */
  opener: HTMLElement | null
  onClose: () => void
}

/** A DaisyUI `menu` placed at a point. Escape, a click outside, a scroll or a resize close it; the arrow keys move between items. */
export function ContextMenu({ x, y, items, opener, onClose }: Props) {
  const list = useRef<HTMLUListElement>(null)

  // keep the menu inside the window
  useLayoutEffect(() => {
    const menu = list.current
    if (!menu) return
    menu.style.left = `${Math.max(8, Math.min(x, window.innerWidth - menu.offsetWidth - 8))}px`
    menu.style.top = `${Math.max(8, Math.min(y, window.innerHeight - menu.offsetHeight - 8))}px`
    menu.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()
  }, [x, y])

  useEffect(() => {
    const closeOutside = (event: Event) => {
      if (!list.current?.contains(event.target as Node)) onClose()
    }
    document.addEventListener('pointerdown', closeOutside)
    window.addEventListener('scroll', onClose, true)
    window.addEventListener('resize', onClose)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      window.removeEventListener('scroll', onClose, true)
      window.removeEventListener('resize', onClose)
    }
  }, [onClose])

  function close() {
    onClose()
    opener?.focus()
  }

  function onKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')]
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement)
    const move = (to: number) => {
      event.preventDefault()
      buttons[(to + buttons.length) % buttons.length]?.focus()
    }
    if (event.key === 'ArrowDown') move(at + 1)
    else if (event.key === 'ArrowUp') move(at - 1)
    else if (event.key === 'Home') move(0)
    else if (event.key === 'End') move(-1)
    else if (event.key === 'Escape' || event.key === 'Tab') {
      event.preventDefault()
      close()
    }
  }

  return (
    <ul
      ref={list}
      role="menu"
      className="menu menu-sm bg-base-100 rounded-box shadow-lg border border-base-300 fixed z-50 w-44 p-1"
      style={{ left: x, top: y }}
      onKeyDown={onKeyDown}
      onContextMenu={(event) => event.preventDefault()}
    >
      {items.map((item) => (
        <li key={item.label}>
          <button
            type="button"
            role="menuitem"
            className={item.danger ? 'text-error' : ''}
            disabled={item.disabled}
            onClick={() => {
              close()
              item.onSelect()
            }}
          >
            {item.label}
          </button>
        </li>
      ))}
    </ul>
  )
}
