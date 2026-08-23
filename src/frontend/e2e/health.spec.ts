import { expect, test } from '@playwright/test'

/**
 * S0.4 / S0.5 - the browser check.
 *
 * This is deliberately not a mocked component test. It drives a real browser against
 * the nginx-served bundle, so passing proves the whole chain: the page is served, React
 * renders, the /api proxy works, FastAPI answers, and PostgreSQL is reachable. A bare
 * HTTP 200 on the front-end port would prove only the first link.
 */
test('the page renders the backend status fetched from /health', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Logistics Analytics' })).toBeVisible()

  const status = page.getByTestId('backend-status')
  // The text is sourced from the backend response, so asserting on it fails if the
  // proxy, the API, or the database is down.
  await expect(status).toHaveText(/ok · database reachable/, { timeout: 30_000 })
})

test('the front-end proxies /api/health through to the backend', async ({ request }) => {
  const response = await request.get('/api/health')

  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok', database: 'reachable' })
})
