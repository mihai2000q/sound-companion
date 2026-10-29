import { useQuery } from '@tanstack/react-query'
import { AppBar } from '../components/AppBar'
import { credits } from '../lib/credits'
import { monitoringQueries } from '../queries/monitoring'
import { Spinner } from '@/components/ui/spinner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const ms = (value: number) => `${Math.round(value).toLocaleString()} ms`
const count = (value: number) => value.toLocaleString()
const percent = (rate: number) => `${(rate * 100).toFixed(1)}%`

export function MonitoringPage() {
  const { data, error, isFetching, refetch } = useQuery(monitoringQueries.summary())

  return (
    <div className="flex h-full flex-col bg-muted/40">
      <AppBar>
        <Button type="button" variant="outline" size="sm" disabled={isFetching} onClick={() => refetch()}>
          Refresh
        </Button>
      </AppBar>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 p-4">
          <h1 className="text-2xl font-bold">Monitoring</h1>
          {error && <Alert variant="destructive">{error.message}</Alert>}
          {isFetching && !data && <Spinner className="size-6" />}
          {data && (
            <>
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
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Usage per model</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.models.length === 0 ? (
                    <p>No model calls logged yet.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Purpose</TableHead>
                          <TableHead>Model</TableHead>
                          <TableHead className="text-right">Calls</TableHead>
                          <TableHead className="text-right">Tokens in</TableHead>
                          <TableHead className="text-right">Tokens out</TableHead>
                          <TableHead className="text-right">Credits</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.models.map((row) => (
                          <TableRow key={`${row.purpose}/${row.model}`}>
                            <TableCell>{row.purpose}</TableCell>
                            <TableCell>{row.model}</TableCell>
                            <TableCell className="text-right">{count(row.calls)}</TableCell>
                            <TableCell className="text-right">{count(row.prompt_tokens)}</TableCell>
                            <TableCell className="text-right">{count(row.completion_tokens)}</TableCell>
                            <TableCell className="text-right">{credits(row.cost_credits)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
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
                          <TableHead className="text-right">Tokens in</TableHead>
                          <TableHead className="text-right">Tokens out</TableHead>
                          <TableHead className="text-right">Credits</TableHead>
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
                            <TableCell className="text-right">{count(row.prompt_tokens)}</TableCell>
                            <TableCell className="text-right">{count(row.completion_tokens)}</TableCell>
                            <TableCell className="text-right">{credits(row.cost_credits)}</TableCell>
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
      </div>
    </div>
  )
}
