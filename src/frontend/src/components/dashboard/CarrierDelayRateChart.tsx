import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { COLOR_ATTENTION } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'

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
 * The rate is plotted as the ratio the backend sent - `0.2857`, not `28.6%`. Rescaling it
 * in the browser would mean two places in the system deciding how this number is printed,
 * and the row order is the backend's too: it sorted worst first, so the chart never
 * re-sorts and can never disagree with its own data table.
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
        <XAxis type="number" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis
          type="category"
          dataKey="group"
          tickLine={false}
          axisLine={false}
          width={110}
          tickMargin={8}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
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
