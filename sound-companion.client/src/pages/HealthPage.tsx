import { useQuery } from '@tanstack/react-query'
import { AppBar } from '../components/AppBar'
import { Spinner } from '../components/Spinner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { healthQueries } from '../queries/health'
import { HealthError } from '../types/health'

export function HealthPage() {
  const { data, error, isFetching, refetch } = useQuery(healthQueries.status())
  const errorHealth = error instanceof HealthError ? error.health : undefined

  return (
    <main className="min-h-screen flex flex-col bg-muted/40">
      <AppBar />
      <div className="flex-1 grid place-items-center p-4">
        <h1 className="sr-only">Server health</h1>
        <Card className="w-96 max-w-full">
          <CardHeader>
            <CardTitle className="text-lg">Server health</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
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
                  <Badge className="bg-green-600 text-white">{data.status}</Badge>
                </li>
                <li className="flex items-center justify-between">
                  <span>Database</span>
                  <Badge className="bg-green-600 text-white">{data.database}</Badge>
                </li>
              </ul>
            )}

            {!isFetching && error && (
              <Alert variant="destructive">
                <div>
                  <p className="font-semibold">{error.message}</p>
                  {errorHealth && <p>Database: {errorHealth.database}</p>}
                </div>
              </Alert>
            )}
          </CardContent>
          <CardFooter className="justify-end">
            <Button type="button" size="sm" onClick={() => refetch()}>
              Check again
            </Button>
          </CardFooter>
        </Card>
      </div>
    </main>
  )
}
