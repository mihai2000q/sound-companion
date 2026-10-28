import type { ThreadSummary } from '../types/threads'

export interface ThreadGroup {
  label: 'Today' | 'Yesterday' | 'Earlier'
  threads: ThreadSummary[]
}

/** Splits the list (already newest first) by the local calendar day of `created_at`; empty groups are left out. */
export function groupThreads(threads: ThreadSummary[], now = new Date()): ThreadGroup[] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime()
  const groups: ThreadGroup[] = [
    { label: 'Today', threads: [] },
    { label: 'Yesterday', threads: [] },
    { label: 'Earlier', threads: [] },
  ]
  for (const thread of threads) {
    const created = new Date(thread.created_at).getTime()
    groups[created >= today ? 0 : created >= yesterday ? 1 : 2].threads.push(thread)
  }
  return groups.filter((group) => group.threads.length > 0)
}
