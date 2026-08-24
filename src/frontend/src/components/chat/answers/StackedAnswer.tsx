import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { seriesColor } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'
import { humanizeKey } from '@/lib/metricFormat'

type StackedAnswerProps = {
  rows: ChartRow[]
  metrics: string[]
}

/**
 * Answer type 4: two series that add up to a real total.
 *
 * A shared `stackId` is what makes them one bar per bucket rather than two beside it. Both
 * series came back from a single query, so they are bucketed identically by construction -
 * stacking two separately fetched series is how bars stop lining up.
 *
 * The tool guarantees both halves are counts of rows: a pair containing a rate is rejected
 * at the schema, because two percentages stacked on one axis mean nothing.
 */
export function StackedAnswer({ rows, metrics }: StackedAnswerProps) {
  const config = Object.fromEntries(
    metrics.map((metric) => [metric, { label: humanizeKey(metric), color: seriesColor(metric) }]),
  ) satisfies ChartConfig

  return (
    <ChartContainer config={config} className="aspect-auto h-[250px] w-full" data-testid="chat-answer-chart">
      <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="group" tickLine={false} axisLine={false} tickMargin={8} minTickGap={4} />
        <YAxis tickLine={false} axisLine={false} width={32} />
        <ChartTooltip content={<ChartTooltipContent />} />
        {metrics.map((metric) => (
          <Bar
            key={metric}
            dataKey={metric}
            stackId="answer"
            fill={`var(--color-${metric})`}
            isAnimationActive={false}
          />
        ))}
        <ChartLegend content={<ChartLegendContent />} />
      </BarChart>
    </ChartContainer>
  )
}
