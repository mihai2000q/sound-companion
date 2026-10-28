import { useQuery } from '@tanstack/react-query'
import { AppBar } from '../components/AppBar'
import { monitoringQueries } from '../queries/monitoring'

const ms = (value: number) => `${Math.round(value).toLocaleString()} ms`
const percent = (rate: number) => `${(rate * 100).toFixed(1)}%`

export function MonitoringPage() {
  const { data, error, isFetching, refetch } = useQuery(monitoringQueries.summary())

  return (
    <main className="min-h-screen bg-base-200">
      <AppBar>
        <button type="button" className="btn btn-sm" disabled={isFetching} onClick={() => refetch()}>
          Refresh
        </button>
      </AppBar>
      <div className="max-w-3xl mx-auto p-4 flex flex-col gap-4">
        <h1 className="text-2xl font-bold">Monitoring</h1>
        {error && (
          <div role="alert" className="alert alert-error alert-soft">
            {error.message}
          </div>
        )}
        {isFetching && !data && <span className="loading loading-spinner" />}
        {data && (
          <>
            <section className="card bg-base-100 shadow">
              <div className="card-body">
                <h2 className="card-title">Requests per day</h2>
                {data.daily.length === 0 ? (
                  <p>No requests logged yet.</p>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Day</th>
                        <th className="text-right">Requests</th>
                        <th className="text-right">Errors</th>
                        <th className="text-right">Error rate</th>
                        <th className="text-right">Average</th>
                        <th className="text-right">p95</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.daily.map((row) => (
                        <tr key={row.day}>
                          <td>{row.day}</td>
                          <td className="text-right">{row.requests}</td>
                          <td className="text-right">{row.errors}</td>
                          <td className="text-right">{percent(row.error_rate)}</td>
                          <td className="text-right">{ms(row.avg_ms)}</td>
                          <td className="text-right">{ms(row.p95_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
            <section className="card bg-base-100 shadow">
              <div className="card-body">
                <h2 className="card-title">Calls per tool</h2>
                {data.tools.length === 0 ? (
                  <p>No tool calls logged yet.</p>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Tool</th>
                        <th className="text-right">Calls</th>
                        <th className="text-right">Errors</th>
                        <th className="text-right">Average</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.tools.map((row) => (
                        <tr key={row.tool}>
                          <td>{row.tool}</td>
                          <td className="text-right">{row.calls}</td>
                          <td className="text-right">{row.errors}</td>
                          <td className="text-right">{ms(row.avg_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  )
}
