import { useState, type KeyboardEvent, type SubmitEvent } from 'react'

interface Props {
  disabled: boolean
  onSend: (text: string) => void
}

export function Composer({ disabled, onSend }: Props) {
  const [text, setText] = useState('')

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="flex gap-2 p-4 border-t border-base-300"
      onSubmit={(event: SubmitEvent) => {
        event.preventDefault()
        submit()
      }}
    >
      <textarea
        className="textarea textarea-bordered flex-1"
        rows={2}
        placeholder="Ask about music theory or an instrument"
        value={text}
        disabled={disabled}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="submit" className="btn btn-primary self-end" disabled={disabled || !text.trim()}>
        Send
      </button>
    </form>
  )
}
