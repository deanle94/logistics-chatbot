import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { COLOR_ATTENTION } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'
import { formatMetricValue } from '@/lib/metricFormat'

type CarrierDelayRateChartProps = {
  rows: ChartRow[]
}

const CONFIG = {
  delay_rate: { label: 'Delay rate', color: COLOR_ATTENTION },
} satisfies ChartConfig

/**
 * Chart 3: the share of finished orders arriving late, per carrier, worst first (D14).
 *
 * Horizontal bars, matching the design: carrier names are words of very different lengths,
 * and reading them along a vertical axis beats rotating them under a vertical bar.
 *
 * The rate is plotted as the number the backend sent - `28.57`, already a percentage
 * (decision D19b). This file appends the `%` sign and nothing else: rescaling in the browser
 * would mean two places in the system deciding what this number is, and the Slice 2 chat
 * would then quote a different figure from the dashboard. The row order is the backend's
 * too - it sorted worst first, so the chart never re-sorts and can never disagree with its
 * own data table.
 */
export function CarrierDelayRateChart({ rows }: CarrierDelayRateChartProps) {
  return (
    <ChartContainer
      config={CONFIG}
      className="aspect-auto h-72 w-full"
      data-testid="carrier-delay-rate-chart"
    >
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
      >
        <CartesianGrid horizontal={false} />
        <XAxis
          type="number"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(value: number) => formatMetricValue('delay_rate', value)}
        />
        <YAxis
          type="category"
          dataKey="group"
          tickLine={false}
          axisLine={false}
          width={110}
          tickMargin={8}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => (
                <span className="tabular-nums">
                  {formatMetricValue('delay_rate', value as number)}
                </span>
              )}
            />
          }
        />
        <Bar
          dataKey="delay_rate"
          fill="var(--color-delay_rate)"
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartContainer>
  )
}
