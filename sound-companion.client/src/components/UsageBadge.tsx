import type { Usage } from '../types/chat'

/** Credits are tiny per call, so show enough digits for a turn to be visible. */
function credits(value: number): string {
  return value === 0 ? '0' : value < 0.0001 ? value.toExponential(1) : value.toFixed(4)
}

export function UsageBadge({ usage }: { usage: Usage }) {
  return (
    <div className="flex items-center gap-2 text-xs" aria-label="Usage">
      <span className="opacity-70" title="Credits spent by this answer">
        This turn: {credits(usage.cost)}
      </span>
      <span className="badge badge-outline badge-sm" title="Credits spent in total (database sum)">
        Total: {credits(usage.totalSpend)}
      </span>
    </div>
  )
}
