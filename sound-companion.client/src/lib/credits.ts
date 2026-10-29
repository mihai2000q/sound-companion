/** Credits are tiny per call, so show enough digits for a turn to be visible. */
export function credits(value: number): string {
  return value === 0 ? '0' : value < 0.0001 ? value.toExponential(1) : value.toFixed(4)
}
