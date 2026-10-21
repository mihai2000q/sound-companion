import { QueryClient } from '@tanstack/react-query'

// App-wide defaults. A query overrides them in its own queryOptions (see src/queries).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // fresh for 30 s, no refetch on remount inside that window
      gcTime: 5 * 60_000, // unused cache entries live 5 min (the library default, stated on purpose)
      retry: 1,
      refetchOnWindowFocus: false, // local single-user app, no background churn
    },
  },
})
