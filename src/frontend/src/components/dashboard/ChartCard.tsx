import type { ReactNode } from 'react'

import { ChartDataTable } from '@/components/dashboard/ChartDataTable'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { ChartResponse, ChartRow } from '@/lib/api'
import type { RemoteData } from '@/hooks/useRemoteData'

type ChartCardProps = {
  testId: string
  title: string
  subtitle: string
  badgeLabel: string
  state: RemoteData<ChartResponse>
  className?: string
  children: (rows: ChartRow[]) => ReactNode
}

/**
 * The frame every chart on the dashboard sits in: title, subtitle, display-type badge, the
 * chart itself, and the data-table drawer underneath (decision D16).
 *
 * `children` is a function of the rows rather than plain nodes. That keeps loading, error
 * and "no rows" handling in this one place instead of being repeated in all three chart
 * components, while each chart component stays a pure renderer of rows (react rule 1).
 *
 * An empty result is a normal 200 with the params still echoed (decision D15), so it gets
 * a message and a still-usable table - never an error.
 */
export function ChartCard({
  testId,
  title,
  subtitle,
  badgeLabel,
  state,
  className,
  children,
}: ChartCardProps) {
  return (
    <Card className={cn('gap-4 rounded-xl py-6', className)} data-testid={testId}>
      <CardHeader className="gap-1 px-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-base leading-[22px] font-semibold tracking-tight">{title}</span>
            <span className="text-sm leading-5 text-muted-foreground">{subtitle}</span>
          </div>
          <div
            className="inline-flex h-[22px] shrink-0 items-center rounded-lg border px-2 text-xs font-medium text-muted-foreground"
            data-testid={`${testId}-type-badge`}
          >
            {badgeLabel}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 px-6">
        {state.kind === 'loading' && (
          <p className="py-16 text-center text-sm text-muted-foreground">Loading&hellip;</p>
        )}

        {state.kind === 'error' && (
          <p
            className="py-16 text-center text-sm text-destructive"
            data-testid={`${testId}-error`}
          >
            Could not load this chart: {state.message}
          </p>
        )}

        {state.kind === 'loaded' && state.data.rows.length === 0 && (
          <p
            className="py-16 text-center text-sm text-muted-foreground"
            data-testid={`${testId}-empty`}
          >
            No rows matched this question.
          </p>
        )}

        {state.kind === 'loaded' && state.data.rows.length > 0 && children(state.data.rows)}

        {state.kind === 'loaded' && (
          <ChartDataTable testId={testId} rows={state.data.rows} params={state.data.params} />
        )}
      </CardContent>
    </Card>
  )
}
