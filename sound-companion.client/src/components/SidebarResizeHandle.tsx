import type { KeyboardEvent, PointerEvent } from 'react'

export const SIDEBAR_MIN = 224
export const SIDEBAR_MAX = 480
export const SIDEBAR_DEFAULT = 288

interface Props {
  width: number
  onResize: (width: number) => void
  onDraggingChange: (dragging: boolean) => void
}

const clamp = (value: number) => Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, Math.round(value)))

/** A strip on the right edge of the sidebar: drag it, use the arrow keys, or double-click to reset the width. */
export function SidebarResizeHandle({ width, onResize, onDraggingChange }: Props) {
  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId)
    onDraggingChange(true)
  }
  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) onResize(clamp(event.clientX))
  }
  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId)
    onDraggingChange(false)
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowLeft') onResize(clamp(width - 16))
    else if (event.key === 'ArrowRight') onResize(clamp(width + 16))
    else return
    event.preventDefault()
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
      aria-valuemin={SIDEBAR_MIN}
      aria-valuemax={SIDEBAR_MAX}
      aria-valuenow={width}
      tabIndex={0}
      className="absolute inset-y-0 right-0 z-20 hidden w-1.5 cursor-col-resize touch-none transition-colors hover:bg-primary/30 focus-visible:bg-primary/40 focus-visible:outline-none active:bg-primary/50 md:block"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onKeyDown={onKeyDown}
      onDoubleClick={() => onResize(SIDEBAR_DEFAULT)}
    />
  )
}
