import { expect, test } from '@playwright/test'

/**
 * S0.4 / S0.5 - the browser check.
 *
 * This is deliberately not a mocked component test. It drives a real browser against
 * the nginx-served bundle, so passing proves the whole chain: the page is served, React
 * renders, the /api proxy works, FastAPI answers, and PostgreSQL is reachable. A bare
 * HTTP 200 on the front-end port would prove only the first link.
 *
 * Slice 1 removed the header's backend-health badge (decision D19a), so the first test no
 * longer reads `/health` out of the DOM. It reads a KPI instead. That is the same chain
 * asserted more strongly, not less: the badge only proved the database answered `SELECT 1`,
 * while a KPI value can only be right if the rows were seeded, queried and aggregated.
 * The expected value still comes from the live API rather than a literal, so this test
 * cannot pass against a stale bundle showing a cached number.
 */
test('the page renders a KPI fetched through the /api proxy', async ({ page, request }) => {
  const response = await request.get('/api/kpis')
  expect(response.status()).toBe(200)
  const kpis = (await response.json()) as Record<string, { value: number; unit: string | null }>

  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Logistics Analytics' })).toBeVisible()

  // Sourced from the backend response, so this fails if the proxy, the API, the calculator
  // or the database is down.
  await expect(page.getByTestId('kpi-total_orders-value')).toHaveText(
    String(kpis.total_orders.value),
    { timeout: 30_000 },
  )
})

test('the front-end proxies /api/health through to the backend', async ({ request }) => {
  const response = await request.get('/api/health')

  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok', database: 'reachable' })
})
