import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { KpiValue } from '@/lib/api'

/**
 * Props for one KPI tile.
 *
 * `kpi` is nullable because the row renders its five tiles before the response arrives -
 * a placeholder in the right place beats five cards popping into existence.
 */
type KpiCardProps = {
  testId: string
  label: string
  caption: string
  kpi: KpiValue | null
  emphasis: 'default' | 'destructive'
}

/**
 * One KPI tile: label, the number, a caption.
 *
 * The number and its unit are printed **verbatim** from `GET /api/kpis` - no rounding, no
 * scaling, no locale formatting. The calculator already rounded it (decision D13), and
 * re-rounding here is exactly how a dashboard and a chat answer start disagreeing on a
 * digit. That is also why value and unit sit in separate spans: the browser test can then
 * compare the rendered number to the API response with no formatting rule of its own.
 */
export function KpiCard({ testId, label, caption, kpi, emphasis }: KpiCardProps) {
  return (
    <Card className="gap-1.5 rounded-xl py-5" data-testid={testId}>
      <CardContent className="flex flex-col gap-1.5 px-5">
        <span className="text-sm leading-5 text-muted-foreground">{label}</span>
        <span
          className={cn(
            'text-3xl leading-9 font-semibold tracking-tight tabular-nums',
            emphasis === 'destructive' && 'text-destructive',
          )}
        >
          {kpi === null ? (
            <span className="text-muted-foreground">&mdash;</span>
          ) : (
            <>
              <span data-testid={`${testId}-value`}>{kpi.value}</span>
              {kpi.unit !== null && (
                <>
                  {kpi.unit !== '%' && ' '}
                  <span
                    data-testid={`${testId}-unit`}
                    className={kpi.unit === '%' ? undefined : 'text-xl'}
                  >
                    {kpi.unit}
                  </span>
                </>
              )}
            </>
          )}
        </span>
        <span
          className="text-xs leading-4 text-muted-foreground"
          data-testid={`${testId}-caption`}
        >
          {caption}
        </span>
      </CardContent>
    </Card>
  )
}
