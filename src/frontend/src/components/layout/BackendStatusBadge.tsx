import { Badge } from '@/components/ui/badge'
import { useHealth } from '@/hooks/useHealth'

/**
 * Live backend health, shown in the header bar.
 *
 * It owns its own fetch (react rule 6) so a health poll never re-renders the dashboard.
 *
 * The `backend-status` test id and its exact wording are a Slice 0 gate
 * (`e2e/health.spec.ts`), which asserts the whole chain is up - nginx proxy, FastAPI,
 * PostgreSQL - by reading this text. Changing either would break a shipped gate.
 */
export function BackendStatusBadge() {
  const health = useHealth()

  return (
    <span data-testid="backend-status">
      {health.kind === 'loading' && <Badge variant="secondary">checking&hellip;</Badge>}
      {health.kind === 'loaded' && (
        <Badge variant={health.data.status === 'ok' ? 'default' : 'destructive'}>
          {health.data.status} &middot; database {health.data.database}
        </Badge>
      )}
      {health.kind === 'error' && <Badge variant="destructive">unreachable</Badge>}
    </span>
  )
}
