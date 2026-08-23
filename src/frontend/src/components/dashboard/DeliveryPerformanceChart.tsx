import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { COLOR_ATTENTION, COLOR_ON_TIME } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'

type DeliveryPerformanceChartProps = {
  rows: ChartRow[]
}

const CONFIG = {
  delivered_orders: { label: 'On time', color: COLOR_ON_TIME },
  delayed_orders: { label: 'Late', color: COLOR_ATTENTION },
} satisfies ChartConfig

/** Bottom of the stack first, matching both the bars and the design's legend. */
const SERIES_ORDER = ['delivered_orders', 'delayed_orders']

/** Position of a legend entry, derived from the series order rather than its label. */
function legendOrder(item: { dataKey?: string | number | ((row: unknown) => unknown) }): number {
  return SERIES_ORDER.indexOf(String(item.dataKey))
}

/**
 * Chart 2: delivered against delayed per month, stacked.
 *
 * A shared `stackId` is what makes the two series one bar per month: the height is the
 * month's finished orders and the split is the outcome. Both series came back from a single
 * request, so they are guaranteed to be bucketed identically - stacking two separately
 * fetched series is how a chart ends up with bars that do not line up.
 */
export function DeliveryPerformanceChart({ rows }: DeliveryPerformanceChartProps) {
  return (
    <ChartContainer
      config={CONFIG}
      className="aspect-auto h-60 w-full"
      data-testid="delivery-performance-chart"
    >
      <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="group" tickLine={false} axisLine={false} tickMargin={8} minTickGap={4} />
        <YAxis tickLine={false} axisLine={false} width={32} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar
          dataKey="delivered_orders"
          stackId="finished"
          fill="var(--color-delivered_orders)"
          isAnimationActive={false}
        />
        <Bar
          dataKey="delayed_orders"
          stackId="finished"
          fill="var(--color-delayed_orders)"
          radius={[2, 2, 0, 0]}
          isAnimationActive={false}
        />
        {/*
          Recharts sorts legend items alphabetically by label by default, which would put
          "Late" before "On time". Sorting by this chart's own series order instead makes the
          legend read in the design's order and match the stack, and unlike turning sorting
          off entirely it is deterministic across renders.
        */}
        <ChartLegend content={<ChartLegendContent />} itemSorter={legendOrder} />
      </BarChart>
    </ChartContainer>
  )
}
