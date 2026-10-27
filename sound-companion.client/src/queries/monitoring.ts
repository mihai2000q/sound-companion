import { queryOptions } from '@tanstack/react-query'
import type { Monitoring } from '../types/monitoring'

export const monitoringKeys = {
  all: ['monitoring'] as const,
  summary: () => [...monitoringKeys.all, 'summary'] as const,
}

export const monitoringQueries = {
  summary: () =>
    queryOptions({
      queryKey: monitoringKeys.summary(),
      queryFn: async ({ signal }): Promise<Monitoring> => {
        const response = await fetch('/api/monitoring', { signal })
        if (!response.ok) throw new Error(`Server answered ${response.status}`)
        return (await response.json()) as Monitoring
      },
      staleTime: 0, // numbers are read on demand, the button refreshes them
    }),
}
