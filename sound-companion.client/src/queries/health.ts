import { queryOptions } from '@tanstack/react-query'
import { HealthError, type Health } from '../types/health'

// Hierarchical keys: invalidate everything with healthKeys.all, or one entry with healthKeys.status().
export const healthKeys = {
  all: ['health'] as const,
  status: () => [...healthKeys.all, 'status'] as const,
}

export const healthQueries = {
  status: () =>
    queryOptions({
      queryKey: healthKeys.status(),
      queryFn: async ({ signal }): Promise<Health> => {
        const response = await fetch('/api/health', { signal })
        const body = await response.json().catch(() => null)
        if (!response.ok) {
          throw new HealthError(`Server answered ${response.status}`, body?.detail)
        }
        return body as Health
      },
      staleTime: 0, // a health check is only useful fresh
      retry: false, // a 503 is the answer, not a glitch
    }),
}
