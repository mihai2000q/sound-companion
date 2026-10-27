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

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(`/api/threads/${threadId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(`Server answered ${response.status}`)
}

/** The file name is the title (cut, with characters a file system dislikes replaced) and the day. */
export function exportFileName(title: string | null, now = new Date()): string {
  const name = (title ?? '').replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '').slice(0, 50) || 'conversation'
  return `${name}-${now.toISOString().slice(0, 10)}.json`
}

/** Downloads the server's export as it is: the text is saved, not parsed and written again. */
export async function exportThread(thread: { thread_id: string; title: string | null }): Promise<void> {
  const response = await fetch(`/api/threads/${thread.thread_id}/export`)
  if (!response.ok) throw new Error(`Server answered ${response.status}`)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = exportFileName(thread.title)
  link.click()
  URL.revokeObjectURL(url)
}
