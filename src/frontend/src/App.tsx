import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { fetchHealth, type HealthResponse } from '@/lib/api'

type Status =
  | { kind: 'loading' }
  | { kind: 'loaded'; health: HealthResponse }
  | { kind: 'error'; message: string }

/**
 * Slice 0 front-end: prove the React app boots, is served, and can reach the backend.
 *
 * Three explicit states rather than blank-until-loaded, so the browser test asserts on
 * rendered text instead of racing an empty DOM - and so a failure is visible to a human
 * as a failure rather than as a page that never finished.
 */
export default function App() {
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  useEffect(() => {
    let active = true

    fetchHealth()
      .then((health) => {
        if (active) setStatus({ kind: 'loaded', health })
      })
      .catch((error: unknown) => {
        if (active) {
          setStatus({
            kind: 'error',
            message: error instanceof Error ? error.message : 'unknown error',
          })
        }
      })

    // Guard against setting state after unmount in React's development double-render.
    return () => {
      active = false
    }
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          {/*
            shadcn's CardTitle renders a plain div, so an explicit h1 goes inside it:
            the page needs a real heading for assistive technology, and the browser
            test asserts on the heading role rather than on loose text.
          */}
          <CardTitle>
            <h1>Logistics Analytics</h1>
          </CardTitle>
          <CardDescription>Slice 0 skeleton &mdash; structure only</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted-foreground">Backend status</span>
            <span data-testid="backend-status">
              {status.kind === 'loading' && <Badge variant="secondary">checking&hellip;</Badge>}
              {status.kind === 'loaded' && (
                <Badge variant={status.health.status === 'ok' ? 'default' : 'destructive'}>
                  {status.health.status} &middot; database {status.health.database}
                </Badge>
              )}
              {status.kind === 'error' && <Badge variant="destructive">unreachable</Badge>}
            </span>
          </div>
          {status.kind === 'error' && (
            <p className="mt-3 text-xs text-muted-foreground" data-testid="backend-error">
              {status.message}
            </p>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
