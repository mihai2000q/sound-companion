import { useState, type KeyboardEvent, type SubmitEvent } from 'react'
import type { FieldError } from '../hooks/useChatStream'
import { Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  disabled: boolean
  error: FieldError | null
  onSend: (text: string) => Promise<boolean>
  onEdit: () => void
  onStop: () => void
}

export function Composer({ disabled, error, onSend, onEdit, onStop }: Props) {
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
      className="flex flex-col gap-2 border-t p-4"
      onSubmit={(event: SubmitEvent) => {
        event.preventDefault()
        submit()
      }}
    >
      <div className="flex gap-2">
        <Textarea
          className="flex-1 resize-none"
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
        {disabled ? (
          <Button type="button" variant="secondary" size="lg" className="self-end" onClick={onStop}>
            <Square className="fill-current" />
            Stop
          </Button>
        ) : (
          <Button type="submit" size="lg" className="self-end" disabled={!text.trim()}>
            Send
            <Send />
          </Button>
        )}
      </div>
      <p className="text-xs text-muted-foreground">Enter sends, Shift+Enter starts a new line.</p>
      {error && (
        <p role="alert" className="text-destructive text-sm">
          {error.field.charAt(0).toUpperCase() + error.field.slice(1)}: {error.message}
        </p>
      )}
    </form>
  )
}
