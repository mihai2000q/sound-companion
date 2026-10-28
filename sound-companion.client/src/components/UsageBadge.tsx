import type { Usage } from '../types/chat'
import { Badge } from '@/components/ui/badge'

/** Credits are tiny per call, so show enough digits for a turn to be visible. */
function credits(value: number): string {
  return value === 0 ? '0' : value < 0.0001 ? value.toExponential(1) : value.toFixed(4)
}

export function UsageBadge({ usage }: { usage: Usage }) {
  return (
    <div className="flex items-center gap-2 text-xs" aria-label="Usage">
      {usage.warning && (
        <Badge role="status" className="bg-amber-500 text-black">
          Spending limit is close
        </Badge>
      )}
      <span className="text-muted-foreground" title="Credits spent by this answer">
        This turn: {credits(usage.cost)}
      </span>
      <Badge variant="outline" title="Credits spent in total (database sum)">
        Total: {credits(usage.totalSpend)}
      </Badge>
    </div>
  )
}
