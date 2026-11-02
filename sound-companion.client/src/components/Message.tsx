import type { ReactNode } from 'react'
import { Music2 } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '../types/chat'

interface Props {
  role: ChatMessage['role']
  children: ReactNode
  label?: string
}

/** One message of the chat: avatar, name and the text. Yours is a primary bubble, the bot's is serif text beside a brass rule. */
export function Message({ role, children, label }: Props) {
  const user = role === 'user'
  return (
    <div className={cn('flex items-end gap-2', user && 'flex-row-reverse')} aria-label={label}>
      <Avatar className="size-8" aria-hidden="true">
        <AvatarFallback className={cn('text-xs font-medium', !user && 'bg-brass text-brass-foreground')}>
          {user ? 'Me' : <Music2 className="size-4" />}
        </AvatarFallback>
      </Avatar>
      <div className={cn('flex min-w-0 max-w-[85%] flex-col gap-1', user && 'items-end')}>
        <div className="text-xs text-muted-foreground">{user ? 'Me' : 'Sound Companion'}</div>
        <div
          className={cn(
            'break-words',
            user
              ? 'whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2 font-medium text-primary-foreground'
              : 'border-l-2 border-brass pl-4 font-serif text-[1.0625rem] leading-relaxed text-foreground',
          )}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
