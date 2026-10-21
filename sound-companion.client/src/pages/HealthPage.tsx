import { useQuery } from '@tanstack/react-query'
import { healthQueries } from '../queries/health'
import { HealthError } from '../types/health'

export function HealthPage() {
  const { data, error, isFetching, refetch } = useQuery(healthQueries.status())
  const errorHealth = error instanceof HealthError ? error.health : undefined

  return (
    <main className="min-h-screen grid place-items-center bg-base-200 p-4">
      <div className="flex flex-col items-center gap-6">
        <h1 className="text-3xl font-bold">Sound Companion</h1>
        <div className="card bg-base-100 shadow-xl w-96">
          <div className="card-body">
            <h2 className="card-title">Server health</h2>

            {isFetching && (
              <div className="flex items-center gap-2">
                <span className="loading loading-spinner loading-sm" />
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
              <button type="button" className="btn btn-primary btn-sm" onClick={() => refetch()}>
                Check again
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
