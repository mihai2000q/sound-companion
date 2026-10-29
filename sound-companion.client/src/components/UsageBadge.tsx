import { credits } from '../lib/credits'
import type { Usage } from '../types/chat'
import { Badge } from '@/components/ui/badge'

export function UsageBadge({ usage }: { usage: Usage }) {
  return (
    <div className="flex items-center gap-2 text-xs" aria-label="Usage">
      {usage.warning && (
        <Badge role="status" className="bg-amber-500 text-black">
          Spending limit is close
        </Badge>
      )}
      <span className="text-muted-foreground" title="Spent by this answer, in USD">
        This turn: {credits(usage.cost)}
      </span>
      <Badge variant="outline" title="Spent in total, in USD (database sum)">
        Total: {credits(usage.totalSpend)}
      </Badge>
    </div>
  )
}
