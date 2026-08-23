import axios from 'axios'

/**
 * All backend calls go through a relative `/api` path rather than an absolute URL.
 *
 * nginx proxies `/api` to the backend, so browser and API share one origin: the same
 * bundle works in the container, behind a public URL, and in the dev server without a
 * rebuild, and CORS never enters the picture.
 */
export const api = axios.create({
  baseURL: '/api',
  timeout: 10_000,
})

/**
 * One KPI card's number, exactly as `GET /api/kpis` returns it.
 *
 * `unit` is nullable rather than `''` so a bare count is visibly "no unit". The value is
 * already rounded by the calculator (decision D13) - the front-end prints it verbatim and
 * never rounds, scales or reformats it, so the dashboard and the Slice 2 chat can never
 * disagree on a digit.
 */
export interface KpiValue {
  value: number
  unit: string | null
}

/**
 * The five KPIs of `docs/requirement.md` section 2.1, one field each.
 */
export interface KpisResponse {
  total_orders: KpiValue
  delivered_orders: KpiValue
  delayed_orders: KpiValue
  on_time_rate: KpiValue
  average_delivery_time: KpiValue
}

/**
 * One flat chart row: the bucket key plus one entry per requested metric.
 *
 * Flat rather than `{group, values: {...}}` because that is the shape recharts and the
 * data table consume directly - a nested row would have to be unwrapped by every consumer.
 * The index signature is what lets a row carry metric keys the type does not know by name;
 * `params.metrics` is the list that says which keys those are.
 */
export interface ChartRow {
  group: string
  [metric: string]: string | number | null
}

/**
 * The question that produced the rows, echoed back by the backend.
 *
 * This is the explainability mechanism of `docs/requirement.md` section 2.4. `metrics` is
 * always present, even for an empty result, because it is what names the metric keys in a
 * row - without it a caller cannot tell a metric column from the group column.
 */
export interface ChartParams {
  metrics: string[]
  group_by: string
  filters: Record<string, string>
  order: string
}

/**
 * A chart's data and its explanation.
 *
 * An empty `rows` with `params` still filled in is a valid 200 (decision D15), so callers
 * check `rows.length === 0` rather than a status code.
 */
export interface ChartResponse {
  rows: ChartRow[]
  params: ChartParams
}

/**
 * The three parameterless chart routes of decision D9.
 *
 * Listed here rather than spelled out at each call site so the set of routes the dashboard
 * knows about is one readable list, and so a typo is a compile error instead of a 404.
 */
export const CHART_ROUTES = {
  orderVolume: '/dashboard/order-volume',
  deliveryPerformance: '/dashboard/delivery-performance',
  carrierDelayRate: '/dashboard/carrier-delay-rate',
} as const

/**
 * One of the three chart routes.
 */
export type ChartRoute = (typeof CHART_ROUTES)[keyof typeof CHART_ROUTES]

/**
 * Fetch the five dashboard KPIs.
 *
 * Anything other than 200 is a genuine failure here - unlike `/health`, there is no
 * "degraded but meaningful" answer - so axios is left to throw on a bad status.
 */
export async function fetchKpis(): Promise<KpisResponse> {
  const response = await api.get<KpisResponse>('/kpis')
  return response.data
}

/**
 * Fetch one chart's rows and the params that produced them.
 *
 * Takes the route rather than a metric/group-by pair: the generic query engine is
 * deliberately not exposed over HTTP in this slice (decision D10), so the only thing a
 * caller may choose is which of the three fixed questions to ask.
 */
export async function fetchChart(route: ChartRoute): Promise<ChartResponse> {
  const response = await api.get<ChartResponse>(route)
  return response.data
}
