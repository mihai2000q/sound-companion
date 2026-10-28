import { useQuery } from '@tanstack/react-query'
import { AppBar } from '../components/AppBar'
import { monitoringQueries } from '../queries/monitoring'
import { Spinner } from '../components/Spinner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const ms = (value: number) => `${Math.round(value).toLocaleString()} ms`
const percent = (rate: number) => `${(rate * 100).toFixed(1)}%`

export function MonitoringPage() {
  const { data, error, isFetching, refetch } = useQuery(monitoringQueries.summary())

  return (
    <main className="min-h-screen bg-muted/40">
      <AppBar>
        <Button type="button" variant="outline" size="sm" disabled={isFetching} onClick={() => refetch()}>
          Refresh
        </Button>
      </AppBar>
      <div className="max-w-3xl mx-auto p-4 flex flex-col gap-4">
        <h1 className="text-2xl font-bold">Monitoring</h1>
        {error && <Alert variant="destructive">{error.message}</Alert>}
        {isFetching && !data && <Spinner className="size-6" />}
        {data && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Requests per day</CardTitle>
              </CardHeader>
              <CardContent>
                {data.daily.length === 0 ? (
                  <p>No requests logged yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Day</TableHead>
                        <TableHead className="text-right">Requests</TableHead>
                        <TableHead className="text-right">Errors</TableHead>
                        <TableHead className="text-right">Error rate</TableHead>
                        <TableHead className="text-right">Average</TableHead>
                        <TableHead className="text-right">p95</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.daily.map((row) => (
                        <TableRow key={row.day}>
                          <TableCell>{row.day}</TableCell>
                          <TableCell className="text-right">{row.requests}</TableCell>
                          <TableCell className="text-right">{row.errors}</TableCell>
                          <TableCell className="text-right">{percent(row.error_rate)}</TableCell>
                          <TableCell className="text-right">{ms(row.avg_ms)}</TableCell>
                          <TableCell className="text-right">{ms(row.p95_ms)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Calls per tool</CardTitle>
              </CardHeader>
              <CardContent>
                {data.tools.length === 0 ? (
                  <p>No tool calls logged yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tool</TableHead>
                        <TableHead className="text-right">Calls</TableHead>
                        <TableHead className="text-right">Errors</TableHead>
                        <TableHead className="text-right">Average</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.tools.map((row) => (
                        <TableRow key={row.tool}>
                          <TableCell>{row.tool}</TableCell>
                          <TableCell className="text-right">{row.calls}</TableCell>
                          <TableCell className="text-right">{row.errors}</TableCell>
                          <TableCell className="text-right">{ms(row.avg_ms)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </main>
  )
}
