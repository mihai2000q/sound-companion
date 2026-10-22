import { useState, type KeyboardEvent, type SubmitEvent } from 'react'
import type { FieldError } from '../hooks/useChatStream'

interface Props {
  disabled: boolean
  error: FieldError | null
  onSend: (text: string) => Promise<boolean>
  onEdit: () => void
}

export function Composer({ disabled, error, onSend, onEdit }: Props) {
  const [text, setText] = useState('')

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    setText('')
    // A rejected message goes back into the box so it can be fixed.
    void onSend(trimmed).then((accepted) => {
      if (!accepted) setText(trimmed)
    })
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="flex flex-col gap-2 p-4 border-t border-base-300"
      onSubmit={(event: SubmitEvent) => {
        event.preventDefault()
        submit()
      }}
    >
      <div className="flex gap-2">
        <textarea
          className="textarea textarea-bordered flex-1"
          rows={2}
          placeholder="Ask about music theory or an instrument"
          value={text}
          disabled={disabled}
          onChange={(event) => {
            setText(event.target.value)
            onEdit()
          }}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="btn btn-primary self-end" disabled={disabled || !text.trim()}>
          Send
        </button>
      </div>
      {error && (
        <p role="alert" className="text-error text-sm">
          {error.field.charAt(0).toUpperCase() + error.field.slice(1)}: {error.message}
        </p>
      )}
    </form>
  )
}
