import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

/**
 * S3.3 - the acceptance criterion for the forecast card.
 *
 * Same oracle rule as `chat.spec.ts`: nothing here is written down as an expected number.
 * The test captures the browser's own `POST /api/chat` response, parses the result frame,
 * and compares the rendered card to that - "the page shows what the service sent" is the
 * only thing the front-end is responsible for.
 *
 * What IS asserted by name is `docs/requirement.md` section 2.5: all four sections visible
 * and the forecast segment drawn dashed on the one chart. The SKU is the dataset's own -
 * PENCIL-0213 is one of the two SKUs with the three months of history the window needs.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url))
const EVIDENCE_DIR = path.resolve(
  HERE,
  '../../../_1_Tasks/Chat/08_24_2026_21_02_slice3_chat_forecasting/evidence',
)

/** How long one real model answer gets, end to end through the proxy. */
const ANSWER_TIMEOUT = 90_000

/** The design is drawn at 1440x1000; the screenshots are evidence, so they match it. */
test.use({ viewport: { width: 1440, height: 1000 } })
test.setTimeout(180_000)

type ChatRow = { group: string } & Record<string, string | number | null>

type ChatResult = {
  answer: string
  display: string
  data: { metric: string; value: number } | null
  rows: ChatRow[]
  explanation:
    | { metrics: string[]; group_by: string; filters: Record<string, string>; row_count: number }
    | null
  follow_up: { missing_info: string; question: string; options: string[] } | null
  forecast: {
    sku: string
    horizon: number
    window: number
    total: number
    recommended_stock: number
    buffer_pct: number
    methodology: string
  } | null
}

/** Pull the one result frame out of a raw SSE body. */
function resultFrame(body: string): ChatResult {
  const results = body
    .split('\n\n')
    .filter((block) => block.startsWith('event: result'))
    .map((block) => JSON.parse(block.slice(block.indexOf('data:') + 'data:'.length)) as ChatResult)

  expect(results, 'exactly one result frame').toHaveLength(1)
  return results[0]
}

/** Navigate from the dashboard to the chat page the way a person does. */
async function openChat(page: Page): Promise<void> {
  await page.goto('/')
  await page.getByTestId('nav-ask-ai').click()
  await expect(page.getByTestId('chat-page')).toBeVisible()
}

/** Ask one question and return what the service actually answered. */
async function ask(page: Page, question: string): Promise<ChatResult> {
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/chat'), {
    timeout: ANSWER_TIMEOUT,
  })

  await page.getByTestId('chat-input').fill(question)
  await page.getByTestId('chat-submit').click()
  await expect(page.getByTestId('chat-progress-line').first()).toBeVisible({ timeout: 30_000 })

  const body = await (await responsePromise).text()
  await expect(page.getByTestId('chat-answer')).toBeVisible({ timeout: ANSWER_TIMEOUT })
  return resultFrame(body)
}

test('a forecast question renders all four sections with a dashed projection', async ({
  page,
}) => {
  await openChat(page)
  const result = await ask(page, 'Predict demand for PENCIL-0213 for the next 4 months')

  expect(result.display, 'a prediction is a forecast line').toBe('forecast_line')
  expect(result.forecast).not.toBeNull()
  const forecast = result.forecast!
  const forecastRows = result.rows.filter((row) => typeof row.forecast === 'number')
  expect(forecastRows).toHaveLength(forecast.horizon)

  // Section 1 - the forecast values: one tile per projected month, plus the total.
  const values = page.getByTestId('chat-forecast-values')
  await expect(values).toBeVisible()
  await expect(values.getByTestId('chat-forecast-value')).toHaveCount(forecast.horizon)
  await expect(values).toContainText(String(forecast.total))

  // Section 2 - one chart, history solid and the projection dashed. The dashed segment is
  // asserted on the mark itself: a `stroke-dasharray` on a rendered line curve.
  const chart = page.getByTestId('chat-answer-chart')
  await expect(chart).toBeVisible()
  await expect(chart.locator('.recharts-line-curve')).toHaveCount(2)
  await expect(chart.locator('.recharts-line-curve[stroke-dasharray]')).toHaveCount(1)

  // Section 3 - the inventory recommendation, buffer only (review Q2): the recommended
  // figure and the buffer chip, and no lead-time claim anywhere on the card.
  const recommendation = page.getByTestId('chat-forecast-recommendation')
  await expect(recommendation).toBeVisible()
  await expect(recommendation).toContainText(String(forecast.recommended_stock))
  await expect(recommendation).toContainText(`${forecast.buffer_pct}%`)
  await expect(page.getByText(/lead time/i)).toHaveCount(0)

  // Section 4 - the methodology, verbatim from the service: the browser rewrites nothing.
  const methodology = page.getByTestId('chat-forecast-methodology')
  await expect(methodology).toBeVisible()
  await expect(methodology).toContainText(forecast.methodology)

  // The prose is the service's, verbatim.
  await expect(page.getByTestId('chat-answer-text')).toHaveText(result.answer)

  mkdirSync(EVIDENCE_DIR, { recursive: true })
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '06_forecast_card_screenshot.png'),
    fullPage: true,
  })
})
