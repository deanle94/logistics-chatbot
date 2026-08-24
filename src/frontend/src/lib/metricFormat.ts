/**
 * How a metric value is printed. One place, so the chart axis, the tooltip and the data
 * table can never disagree about the same number.
 *
 * This file adds a symbol; it never changes a value. The calculator already returned
 * `28.57` for a 28.57% delay rate (decision D19b) - if this module multiplied, divided or
 * re-rounded anything it would be a second home for a formula, which is exactly what
 * architecture Decision 1 forbids.
 */

/** Metrics the calculator returns already scaled as a percentage (D19b). */
const PERCENT_METRICS: ReadonlySet<string> = new Set(['delay_rate', 'on_time_rate'])

/** What a missing value prints as. SQL returns NULL when a rate has no finished orders. */
const NO_VALUE = '—'

/**
 * Render one metric value for display.
 *
 * Trailing zeros are left exactly as the backend sent them, so `16` prints as "16%" and
 * `28.57` as "28.57%" - the precision carries the information the calculator chose to keep.
 */
export function formatMetricValue(
  metric: string,
  value: string | number | null | undefined,
): string {
  if (value === null || value === undefined) return NO_VALUE
  return PERCENT_METRICS.has(metric) ? `${value}%` : String(value)
}

/** Whether a metric is printed with a percent sign - used for axis ticks. */
export function isPercentMetric(metric: string): boolean {
  return PERCENT_METRICS.has(metric)
}

/**
 * Turn a wire key such as `avg_delivery_time` into the words a person reads.
 *
 * Presentation only. It renames nothing and computes nothing, so no definition escapes the
 * calculator. Slice 2 needs it as a shared helper because the chat labels series it only
 * learns about when the answer arrives.
 */
export function humanizeKey(key: string): string {
  return key.replaceAll('_', ' ')
}
