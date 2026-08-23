import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts'

import { COLOR_ATTENTION } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'

type OrderVolumeChartProps = {
  rows: ChartRow[]
}

/**
 * The config key must equal the metric key on the wire, because shadcn derives the CSS
 * variable name (`--color-order_count`) and the tooltip label from it.
 */
const CONFIG = {
  order_count: { label: 'Orders', color: COLOR_ATTENTION },
} satisfies ChartConfig

/**
 * Chart 1 of `docs/requirement.md` section 2.1: orders per month, as a line.
 *
 * Renders and nothing else (react rule 1) - the fetch lives in `useChart`, the frame in
 * `ChartCard`. It plots the rows it is handed, in the order the backend returned them; the
 * month buckets already arrive chronologically, so no sorting happens in the browser.
 *
 * Animation is off so the chart is fully painted the moment it mounts, which is what makes
 * the Playwright screenshot and the series assertion deterministic rather than a race.
 */
export function OrderVolumeChart({ rows }: OrderVolumeChartProps) {
  return (
    <ChartContainer
      config={CONFIG}
      className="aspect-auto h-60 w-full"
      data-testid="order-volume-chart"
    >
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="group" tickLine={false} axisLine={false} tickMargin={8} minTickGap={16} />
        <YAxis tickLine={false} axisLine={false} width={36} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Line
          dataKey="order_count"
          type="monotone"
          stroke="var(--color-order_count)"
          strokeWidth={2}
          dot={{ r: 3 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  )
}
