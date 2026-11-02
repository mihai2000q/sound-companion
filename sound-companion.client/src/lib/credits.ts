/** OpenRouter credits are shown as US dollars (docs/DECISIONS.md lists "credits equal USD" as still to be confirmed on the account). Tiny per call, so show enough digits for a turn to be visible. */
export function credits(value: number): string {
  if (value === 0) return '$0'
  if (value < 0.000001) return '<$0.000001'
  return `$${value.toFixed(value < 0.0001 ? 6 : 4)}`
}
