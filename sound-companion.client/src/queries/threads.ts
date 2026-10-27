import { queryOptions } from '@tanstack/react-query'
import type { ThreadDetail, ThreadSummary } from '../types/threads'

export const threadKeys = {
  all: ['threads'] as const,
  list: () => [...threadKeys.all, 'list'] as const,
  detail: (threadId: string) => [...threadKeys.all, 'detail', threadId] as const,
}

export const threadQueries = {
  list: () =>
    queryOptions({
      queryKey: threadKeys.list(),
      queryFn: async ({ signal }): Promise<ThreadSummary[]> => {
        const response = await fetch('/api/threads', { signal })
        if (!response.ok) throw new Error(`Server answered ${response.status}`)
        return (await response.json()) as ThreadSummary[]
      },
    }),
  /** `null` for a Conversation the server does not hold yet (a new one). The chat seeds its state from this once,
   *  so a cached copy must never be shown: the entry is dropped as soon as nothing reads it. */
  detail: (threadId: string) =>
    queryOptions({
      queryKey: threadKeys.detail(threadId),
      queryFn: async ({ signal }): Promise<ThreadDetail | null> => {
        const response = await fetch(`/api/threads/${threadId}`, { signal })
        if (response.status === 404) return null
        if (!response.ok) throw new Error(`Server answered ${response.status}`)
        return (await response.json()) as ThreadDetail
      },
      gcTime: 0,
      staleTime: 0,
      retry: false,
      refetchOnReconnect: false,
    }),
}
