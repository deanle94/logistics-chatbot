import { mkdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

/**
 * S1.5 - the acceptance criterion for the dashboard page.
 *
 * Every expected value in this file is read from the running API, never written down as a
 * literal. That is the spec's oracle rule pointed at the browser: a test that hard-codes
 * `400` still passes when the page renders a stale cached number, while a test that compares
 * the card to `GET /api/kpis` fails the moment the two disagree. The only literals here are
 * the field names and the route paths - the wire contract itself.
 *
 * It runs against the live compose stack (`playwright.config.ts` has no `webServer` block on
 * purpose), so passing proves the whole chain: nginx serves the bundle, proxies `/api`,
 * FastAPI answers, the calculator computed, PostgreSQL held the rows.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url))
const EVIDENCE_DIR = path.resolve(
  HERE,
  '../../../_1_Tasks/Dashboard/08_23_2026_slice1_dashboard/evidence',
)

/** The read-only dataset, used here exactly as `conftest.py` uses it: as the oracle. */
const CSV_PATH = path.resolve(HERE, '../../../infra/data/mock_logistics_data.csv')

/** How long the page gets to finish four requests through the proxy on a cold stack. */
const LOAD_TIMEOUT = 30_000

/** The design is drawn at 1440x1000; the screenshots are evidence, so they match it. */
test.use({ viewport: { width: 1440, height: 1000 } })

type KpiValue = { value: number; unit: string | null }

type ChartRow = { group: string } & Record<string, string | number | null>

type ChartResponse = {
  rows: ChartRow[]
  params: { metrics: string[]; group_by: string; filters: Record<string, string>; order: string }
}

/** The five KPI fields of `docs/requirement.md` 2.1, in the order the design shows them. */
const KPI_FIELDS = [
  'total_orders',
  'delivered_orders',
  'delayed_orders',
  'on_time_rate',
  'average_delivery_time',
] as const

/**
 * The three charts, each with the route that feeds it and the SVG element its display type
 * emits.
 *
 * `seriesSelector` is what stops the test passing on an empty chart: recharts always renders
 * the container div and the axes, so asserting on the container proves nothing. The line's
 * dots and the bars' rectangles only exist if there was data to draw.
 */
const CHARTS = [
  {
    testId: 'order-volume',
    route: '/api/dashboard/order-volume',
    chartTestId: 'order-volume-chart',
    seriesSelector: '.recharts-line-dot',
    badge: 'Line',
  },
  {
    testId: 'delivery-performance',
    route: '/api/dashboard/delivery-performance',
    chartTestId: 'delivery-performance-chart',
    seriesSelector: '.recharts-bar-rectangle',
    badge: 'Stacked',
  },
  {
    testId: 'carrier-delay-rate',
    route: '/api/dashboard/carrier-delay-rate',
    chartTestId: 'carrier-delay-rate-chart',
    seriesSelector: '.recharts-bar-rectangle',
    badge: 'Bar',
  },
] as const

/**
 * How many marks the chart for this response should draw.
 *
 * Derived from the response, not counted by hand. Recharts draws one dot per point on a
 * line, and one rectangle per metric value per row on a bar chart - except that a zero-sized
 * rectangle is dropped rather than drawn, which is why zero and null values are excluded
 * here. Getting that right is what lets this assert an exact count instead of a vague
 * "more than nothing".
 */
function expectedMarkCount(chartTestId: string, body: ChartResponse): number {
  if (chartTestId === 'order-volume-chart') {
    return body.rows.length
  }
  return body.rows.reduce((marks, row) => {
    const drawn = body.params.metrics.filter((metric) => {
      const value = row[metric]
      return typeof value === 'number' && value > 0
    })
    return marks + drawn.length
  }, 0)
}

/**
 * The two dataset facts the design prints as copy, counted from the CSV.
 *
 * Only the first four columns are read, and none of them can contain a comma, so a split
 * is enough — the quoted fields in this file (`origin_city`, `destination_city`) sit after
 * `delivery_date`. Pulling in a CSV parser to reach column 3 would be more machinery than
 * the assertion is worth.
 */
function datasetFacts(): { totalRows: number; rowsWithBothDates: number } {
  const lines = readFileSync(CSV_PATH, 'utf8')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
  const rows = lines.slice(1).map((line) => line.split(','))
  return {
    totalRows: rows.length,
    rowsWithBothDates: rows.filter((cells) => cells[2] !== '' && cells[3] !== '').length,
  }
}

/** Fetch one chart route through the front-end's own `/api` proxy and check it answered. */
async function getChart(request: APIRequestContext, route: string): Promise<ChartResponse> {
  const response = await request.get(route)
  expect(response.status(), `${route} should answer 200`).toBe(200)
  return (await response.json()) as ChartResponse
}

/**
 * Wait until the whole page has real data on it.
 *
 * The screenshots are evidence, so they must not be taken mid-load; and the toggle
 * assertions must not race the fetch that fills the table.
 */
async function waitForLoadedDashboard(page: Page): Promise<void> {
  await expect(page.getByTestId('kpi-total_orders-value')).not.toBeEmpty({ timeout: LOAD_TIMEOUT })
  for (const chart of CHARTS) {
    await expect(page.getByTestId(chart.chartTestId)).toBeVisible({ timeout: LOAD_TIMEOUT })
    await expect(page.getByTestId(`${chart.testId}-table-toggle`)).toBeVisible({
      timeout: LOAD_TIMEOUT,
    })
  }
}

test('the five KPI cards show exactly what /api/kpis returned', async ({ page, request }) => {
  const response = await request.get('/api/kpis')
  expect(response.status()).toBe(200)
  const kpis = (await response.json()) as Record<string, KpiValue>

  // All five must be there - requirement 2.1 calls a missing KPI a checklist failure.
  expect(Object.keys(kpis).sort()).toEqual([...KPI_FIELDS].sort())

  await page.goto('/')

  for (const field of KPI_FIELDS) {
    const kpi = kpis[field]
    const card = page.getByTestId(`kpi-${field}`)
    await expect(card, `card for ${field}`).toBeVisible()

    // The number is compared to the API response, printed verbatim on both sides. If the
    // front-end ever rounds, scales or locale-formats it, this line fails.
    await expect(card.getByTestId(`kpi-${field}-value`)).toHaveText(String(kpi.value), {
      timeout: LOAD_TIMEOUT,
    })

    const unit = card.getByTestId(`kpi-${field}-unit`)
    if (kpi.unit === null) {
      await expect(unit, `${field} has no unit`).toHaveCount(0)
    } else {
      await expect(unit, `${field} unit`).toHaveText(kpi.unit)
    }
  }
})

test('the line, stacked bar and bar charts all draw real series', async ({ page, request }) => {
  await page.goto('/')

  for (const chart of CHARTS) {
    const body = await getChart(request, chart.route)
    expect(body.rows.length, `${chart.route} returned rows`).toBeGreaterThan(0)

    const card = page.getByTestId(chart.testId)
    await expect(card).toBeVisible()
    await expect(card.getByTestId(`${chart.testId}-type-badge`)).toHaveText(chart.badge)

    const container = page.getByTestId(chart.chartTestId)
    await expect(container).toBeVisible({ timeout: LOAD_TIMEOUT })

    // The marks themselves, not the container: a chart with no data still renders its div.
    await expect(container.locator(chart.seriesSelector)).toHaveCount(
      expectedMarkCount(chart.chartTestId, body),
      { timeout: LOAD_TIMEOUT },
    )
  }

  // The line chart must actually be a line, and the bar charts bars - the three fixed
  // display types are the front-end's job under decision D9.
  await expect(page.getByTestId('order-volume-chart').locator('.recharts-line-curve')).toHaveCount(1)
  await expect(
    page.getByTestId('delivery-performance-chart').locator('.recharts-line-curve'),
  ).toHaveCount(0)
})

test('the delivery-performance bars are stacked, not drawn side by side', async ({
  page,
  request,
}) => {
  const body = await getChart(request, '/api/dashboard/delivery-performance')

  // Recharts drops a zero-height rectangle instead of drawing it, so the index of a row's
  // rectangle inside its series is the count of earlier rows that had something to draw.
  const drawn = (metric: string) =>
    body.rows.map((row) => typeof row[metric] === 'number' && (row[metric] as number) > 0)
  const deliveredDrawn = drawn('delivered_orders')
  const delayedDrawn = drawn('delayed_orders')
  const rowIndex = body.rows.findIndex((_, index) => deliveredDrawn[index] && delayedDrawn[index])
  expect(rowIndex, 'a month with both a delivered and a delayed bar').toBeGreaterThanOrEqual(0)

  const indexWithin = (flags: boolean[]) => flags.slice(0, rowIndex).filter(Boolean).length

  await page.goto('/')
  await waitForLoadedDashboard(page)

  const series = page.getByTestId('delivery-performance-chart').locator('g.recharts-bar')
  await expect(series, 'one <g> per stacked series').toHaveCount(2)

  const bottom = await series
    .nth(0)
    .locator('.recharts-bar-rectangle')
    .nth(indexWithin(deliveredDrawn))
    .boundingBox()
  const top = await series
    .nth(1)
    .locator('.recharts-bar-rectangle')
    .nth(indexWithin(delayedDrawn))
    .boundingBox()

  expect(bottom).not.toBeNull()
  expect(top).not.toBeNull()
  if (bottom === null || top === null) return

  // Geometry only a stack can satisfy. Grouped bars for the same month would sit at
  // different x positions and share a baseline instead of touching; this asserts they
  // share the x band and that the late bar's bottom edge is the on-time bar's top edge.
  // Without it, "line + stacked + bar" is only ever proved as "line + bar + bar", since
  // the mark count is identical either way and the `Stacked` badge is hardcoded copy.
  expect(Math.abs(top.x - bottom.x), 'same x band').toBeLessThanOrEqual(1)
  expect(Math.abs(top.width - bottom.width), 'same bar width').toBeLessThanOrEqual(1)
  expect(Math.abs(top.y + top.height - bottom.y), 'late sits on top of on time').toBeLessThanOrEqual(
    1,
  )
})

test('a chart tooltip prints the number the route sent, undecorated', async ({ page, request }) => {
  const body = await getChart(request, '/api/dashboard/carrier-delay-rate')
  const worst = body.rows[0]
  expect(typeof worst.delay_rate, 'the worst carrier has a rate').toBe('number')

  await page.goto('/')
  await waitForLoadedDashboard(page)

  const card = page.getByTestId('carrier-delay-rate')
  await card.getByTestId('carrier-delay-rate-chart').locator('.recharts-bar-rectangle').first()
    .hover()

  // The registry tooltip shipped `toLocaleString()`, which defaults to three fraction
  // digits and would print `28.571` for a `28.57` the table one drawer below shows in full.
  // A number is rounded once, in `calculator/` (D13); the browser reformats nothing and
  // only appends the `%` sign (D19b).
  // Scoped to this card: every chart renders its own (mostly empty) tooltip wrapper.
  const shown = `${worst.delay_rate}%`
  const tooltip = card.locator('.recharts-tooltip-wrapper', { hasText: String(worst.group) })
  await expect(tooltip).toContainText(shown)

  // Same page, same number: the tooltip and the data table must not disagree on a digit.
  await card.getByTestId('carrier-delay-rate-table-toggle').click()
  const firstRow = card.getByTestId('carrier-delay-rate-table-row').first()
  await expect(firstRow).toContainText(shown)
})

test('the dataset counts printed as copy still describe the dataset', async ({ page, request }) => {
  const response = await request.get('/api/kpis')
  expect(response.status()).toBe(200)
  const kpis = (await response.json()) as Record<string, KpiValue>
  const facts = datasetFacts()

  await page.goto('/')
  await waitForLoadedDashboard(page)

  // The design prints these totals as static copy (`docs/design/Main.dc.html`), because
  // recomputing "finished" in the browser would put a business definition outside
  // `calculator/`. Static is fine; silently stale is not — so each figure is tied to the
  // live API or to the CSV oracle, and re-seeding with different data fails here.
  const finished = kpis.delivered_orders.value + kpis.delayed_orders.value
  await expect(page.getByTestId('kpi-on_time_rate-caption')).toHaveText(
    `${kpis.delivered_orders.value} on time of ${finished} finished`,
  )
  await expect(page.getByTestId('kpi-average_delivery_time-caption')).toHaveText(
    `Across ${facts.rowsWithBothDates} orders with dates`,
  )
  await expect(page.getByTestId('dataset-summary')).toHaveText(
    `${facts.totalRows} rows · read-only`,
  )
  await expect(page.getByTestId('kpi-total_orders-value')).toHaveText(String(facts.totalRows))
})

test('each data table reveals one row per row its own chart route returned', async ({
  page,
  request,
}) => {
  await page.goto('/')
  await waitForLoadedDashboard(page)

  for (const chart of CHARTS) {
    const body = await getChart(request, chart.route)

    const rows = page.getByTestId(`${chart.testId}-table-row`)
    // Collapsed by default (decision D16) - nothing is revealed until it is asked for.
    await expect(rows).toHaveCount(0)

    await page.getByTestId(`${chart.testId}-table-toggle`).click()

    const table = page.getByTestId(`${chart.testId}-table`)
    await expect(table).toBeVisible()
    await expect(rows, `${chart.route} row count`).toHaveCount(body.rows.length)

    // A header row on top of the data rows, and the columns the params said to show.
    await expect(table.locator('thead tr')).toHaveCount(1)
    await expect(table.locator('thead th')).toHaveCount(body.params.metrics.length + 1)

    await page.getByTestId(`${chart.testId}-table-toggle`).click()
    await expect(rows).toHaveCount(0)
  }
})

test('capture the dashboard evidence screenshots', async ({ page }) => {
  mkdirSync(EVIDENCE_DIR, { recursive: true })

  await page.goto('/')
  await waitForLoadedDashboard(page)

  // 06 - the whole page as a reviewer first sees it, every table drawer shut.
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '06_dashboard_screenshot.png'),
    fullPage: true,
  })

  // 07 - the same page with one drawer open, because the toggle is invisible in 06.
  await page.getByTestId('order-volume-table-toggle').click()
  await expect(page.getByTestId('order-volume-table')).toBeVisible()
  await expect(page.getByTestId('order-volume-table-row').first()).toBeVisible()

  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '07_table_toggle_screenshot.png'),
    fullPage: true,
  })
})
