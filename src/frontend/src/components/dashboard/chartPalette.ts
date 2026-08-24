/**
 * The two series colours of `docs/design/Main.dc.html`.
 *
 * They live here rather than in `index.css` because the project's `--chart-1..5` tokens are
 * the greyscale ramp of the installed shadcn style, and every other Slice 0 surface depends
 * on that theme. Two named constants keep the design's palette out of three chart files
 * without repainting a global token that something else might be using tomorrow.
 */

/** Delivered / on-time - the calm series. */
export const COLOR_ON_TIME = 'oklch(0.6 0.118 184.704)'

/** Delayed, and the single-series charts - the series the manager is looking for. */
export const COLOR_ATTENTION = 'oklch(0.646 0.222 41.116)'

/**
 * Metrics that describe things going right. Everything else gets the attention colour.
 *
 * Slice 2 needs this as a lookup rather than a constant per chart: the chat draws series
 * it only learns about at runtime, from `explanation.metrics`. The pairing itself is
 * unchanged - teal good, orange bad, and it never flips anywhere in the app.
 */
const CALM_METRICS: ReadonlySet<string> = new Set(['delivered_orders', 'on_time_rate'])

/** The colour a series is drawn in, chosen by what the series means. */
export function seriesColor(metric: string): string {
  return CALM_METRICS.has(metric) ? COLOR_ON_TIME : COLOR_ATTENTION
}
