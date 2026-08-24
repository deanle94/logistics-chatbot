import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { seriesColor } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'
import { formatMetricValue, humanizeKey } from '@/lib/metricFormat'

type BarAnswerProps = {
  rows: ChartRow[]
  metric: string
}

/**
 * Answer type 3: categories with no natural order, compared.
 *
 * Horizontal bars and one colour, following the design: the categories are peers, so
 * colouring them differently would imply a meaning that is not there, and category names
 * read better along the axis than rotated beneath it. The row order is the backend's - it
 * sorted worst first - so this never re-sorts and cannot disagree with its own data table.
 */
export function BarAnswer({ rows, metric }: BarAnswerProps) {
  const config = {
    [metric]: { label: humanizeKey(metric), color: seriesColor(metric) },
  } satisfies ChartConfig

  return (
    <ChartContainer config={config} className="aspect-auto h-[250px] w-full" data-testid="chat-answer-chart">
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid horizontal={false} />
        <XAxis
          type="number"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(value: number) => formatMetricValue(metric, value)}
        />
        <YAxis type="category" dataKey="group" tickLine={false} axisLine={false} width={110} tickMargin={8} />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => (
                <span className="tabular-nums">{formatMetricValue(metric, value as number)}</span>
              )}
            />
          }
        />
        <Bar
          dataKey={metric}
          fill={`var(--color-${metric})`}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartContainer>
  )
}
