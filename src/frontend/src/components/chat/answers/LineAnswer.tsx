import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts'

import { seriesColor } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'
import { humanizeKey } from '@/lib/metricFormat'

type LineAnswerProps = {
  rows: ChartRow[]
  metric: string
}

/**
 * Answer type 2: one series moving through time.
 *
 * The config key has to equal the metric key on the wire, because shadcn derives both the
 * CSS variable and the tooltip label from it. Unlike the dashboard's charts that key is not
 * known until the answer arrives, so the config is built per render from `explanation`.
 */
export function LineAnswer({ rows, metric }: LineAnswerProps) {
  const config = {
    [metric]: { label: humanizeKey(metric), color: seriesColor(metric) },
  } satisfies ChartConfig

  return (
    <ChartContainer config={config} className="aspect-auto h-[250px] w-full" data-testid="chat-answer-chart">
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="group" tickLine={false} axisLine={false} tickMargin={8} minTickGap={16} />
        <YAxis tickLine={false} axisLine={false} width={36} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Line
          dataKey={metric}
          type="monotone"
          stroke={`var(--color-${metric})`}
          strokeWidth={2}
          dot={{ r: 3 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  )
}
