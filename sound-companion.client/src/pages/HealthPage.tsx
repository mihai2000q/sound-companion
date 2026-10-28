import { useQuery } from '@tanstack/react-query'
import { AppBar } from '../components/AppBar'
import { healthQueries } from '../queries/health'
import { HealthError } from '../types/health'
import { Spinner } from '../components/Spinner'
import { Button } from '@/components/ui/button'

export function HealthPage() {
  const { data, error, isFetching, refetch } = useQuery(healthQueries.status())
  const errorHealth = error instanceof HealthError ? error.health : undefined

  return (
    <main className="min-h-screen flex flex-col bg-base-200">
      <AppBar />
      <div className="flex-1 grid place-items-center p-4">
        <h1 className="sr-only">Server health</h1>
        <div className="card bg-base-100 shadow-xl w-96">
          <div className="card-body">
            <h2 className="card-title">Server health</h2>

            {isFetching && (
              <div className="flex items-center gap-2">
                <Spinner />
                <span>Checking...</span>
              </div>
            )}

            {!isFetching && !error && data && (
              <ul className="flex flex-col gap-2">
                <li className="flex items-center justify-between">
                  <span>Server</span>
                  <span className="badge badge-success">{data.status}</span>
                </li>
                <li className="flex items-center justify-between">
                  <span>Database</span>
                  <span className="badge badge-success">{data.database}</span>
                </li>
              </ul>
            )}

            {!isFetching && error && (
              <div role="alert" className="alert alert-error alert-soft">
                <div>
                  <p className="font-semibold">{error.message}</p>
                  {errorHealth && <p>Database: {errorHealth.database}</p>}
                </div>
              </div>
            )}

            <div className="card-actions justify-end">
              <Button type="button" size="sm" onClick={() => refetch()}>
                Check again
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
