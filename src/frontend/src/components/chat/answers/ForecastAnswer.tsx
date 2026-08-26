import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts'

import { COLOR_ATTENTION, COLOR_ON_TIME } from '@/components/dashboard/chartPalette'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { ChartRow } from '@/lib/api'
import type { ChatForecast } from '@/lib/chatApi'

type ForecastAnswerProps = {
  rows: ChartRow[]
  forecast: ChatForecast
}

/** The two series of the one chart, keyed exactly as the wire keys them (decision D28). */
const CONFIG = {
  quantity: { label: 'Actual demand', color: COLOR_ATTENTION },
  forecast: { label: 'Forecast', color: COLOR_ON_TIME },
} satisfies ChartConfig

/**
 * Answer type 5 of `docs/design/AnswerTypes.dc.html`, laid out per `ChatForecast.dc.html`:
 * the four sections requirement 2.5 demands - values, one chart, recommendation,
 * methodology.
 *
 * The wire carries ONE `rows` array under two value keys (`quantity` for recorded months,
 * `forecast` for projected ones), so which series a point belongs to is data, not
 * inference. The bridge point - the dashed line starting at the last solid point - is
 * derived here rather than sent, because it is presentation: duplicating a measured value
 * under the `forecast` key on the wire would make one month look both measured and
 * projected to every other consumer.
 *
 * Deliberate deviation from the design mock (spec review Q2): the recommendation is
 * buffer-only. No reorder point and no lead-time chip - the mock's 20-day lead time is an
 * invented constant the orders do not state.
 */
export function ForecastAnswer({ rows, forecast }: ForecastAnswerProps) {
  const history = rows.filter((row) => typeof row.quantity === 'number')
  const projected = rows.filter((row) => typeof row.forecast === 'number')
  const chartData = [
    ...history.map((row, index) =>
      index === history.length - 1 ? { ...row, forecast: row.quantity } : row,
    ),
    ...projected,
  ]

  return (
    <div className="flex flex-col gap-4" data-testid="chat-answer-forecast">
      {/* Section 1 - the projected values, one tile per month plus the total. */}
      <div className="flex flex-wrap gap-2" data-testid="chat-forecast-values">
        {projected.map((row) => (
          <div
            key={row.group}
            className="flex min-w-20 flex-col gap-0.5 rounded-lg border px-3 py-2"
            data-testid="chat-forecast-value"
          >
            <span className="text-xs text-muted-foreground">{row.group}</span>
            <span className="text-lg font-semibold tabular-nums">{row.forecast}</span>
          </div>
        ))}
        <div className="flex min-w-20 flex-col gap-0.5 rounded-lg border bg-muted/40 px-3 py-2">
          <span className="text-xs text-muted-foreground">Total</span>
          <span className="text-lg font-semibold tabular-nums" data-testid="chat-forecast-total">
            {forecast.total}
          </span>
        </div>
      </div>

      {/* Section 2 - one chart: recorded months solid, the projection dashed. */}
      <ChartContainer
        config={CONFIG}
        className="aspect-auto h-[250px] w-full"
        data-testid="chat-answer-chart"
      >
        <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="group" tickLine={false} axisLine={false} tickMargin={8} minTickGap={16} />
          <YAxis tickLine={false} axisLine={false} width={36} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Line
            dataKey="quantity"
            type="monotone"
            stroke="var(--color-quantity)"
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
          <Line
            dataKey="forecast"
            type="monotone"
            stroke="var(--color-forecast)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ChartContainer>

      {/* Section 3 - the inventory recommendation, buffer only (review Q2). */}
      <div
        className="flex flex-col gap-2 rounded-lg border px-4 py-3"
        data-testid="chat-forecast-recommendation"
      >
        <span className="text-xs font-medium text-muted-foreground">Inventory recommendation</span>
        <p className="text-sm">
          Stock{' '}
          <span className="font-semibold tabular-nums">{forecast.recommended_stock} units</span> to
          cover the {forecast.horizon}-month horizon &mdash; the {forecast.total}-unit forecast
          plus the safety buffer.
        </p>
        <span className="inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
          safety buffer {forecast.buffer_pct}% &mdash; our assumption
        </span>
      </div>

      {/* Section 4 - the methodology, verbatim from the calculator. */}
      <div
        className="flex flex-col gap-1 rounded-lg bg-muted/40 px-4 py-3"
        data-testid="chat-forecast-methodology"
      >
        <span className="text-xs font-medium text-muted-foreground">
          How this projection was worked out
        </span>
        <p className="text-sm text-muted-foreground">{forecast.methodology}</p>
      </div>
    </div>
  )
}
