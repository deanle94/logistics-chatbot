import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

/**
 * S2.6 - the acceptance criterion for the chat page.
 *
 * Same oracle rule as `dashboard.spec.ts`, pointed at a stream: nothing here is written
 * down as an expected number. Each test captures the browser's own `POST /api/chat`
 * response, parses the result frame out of it, and compares the rendered page to that. So
 * the assertion is "the page shows what the service sent", which is the only thing the
 * front-end is responsible for - and it holds whatever the model happened to answer.
 *
 * It runs against the live compose stack and a real model call, so the timeouts are
 * generous and the questions are few: every one of them costs money.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url))
const EVIDENCE_DIR = path.resolve(
  HERE,
  '../../../_1_Tasks/Chat/08_24_2026_slice2_chat_queries/evidence',
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

/**
 * Ask one question and return what the service actually answered.
 *
 * The progress assertion happens here rather than in each test because it has to happen
 * *while* the answer is still being worked out - once the card renders there is nothing
 * left to observe, so checking it afterwards would silently pass on a page that never
 * showed progress at all.
 */
async function ask(page: Page, question: string): Promise<ChatResult> {
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/chat'), {
    timeout: ANSWER_TIMEOUT,
  })

  await page.getByTestId('chat-input').fill(question)
  await page.getByTestId('chat-submit').click()

  // At least one progress line, before any answer exists to replace it.
  await expect(page.getByTestId('chat-progress-line').first()).toBeVisible({ timeout: 30_000 })

  const body = await (await responsePromise).text()
  await expect(page.getByTestId('chat-answer')).toBeVisible({ timeout: ANSWER_TIMEOUT })
  return resultFrame(body)
}

test('a carrier question renders a bar chart, its working, and its rows', async ({ page }) => {
  await openChat(page)
  const result = await ask(page, 'Which carrier has the highest delay rate?')

  expect(result.display, 'a comparison of peers is a bar').toBe('bar')
  expect(result.explanation?.group_by).toBe('carrier')
  expect(result.rows.length).toBeGreaterThan(0)

  // The marks themselves, not the container: an empty chart still renders its div.
  const chart = page.getByTestId('chat-answer-chart')
  await expect(chart).toBeVisible()
  await expect(chart.locator('.recharts-bar-rectangle')).toHaveCount(
    result.rows.filter((row) => typeof row.delay_rate === 'number' && row.delay_rate > 0).length,
  )

  // The prose is the service's, verbatim - the browser never rewrites an answer.
  await expect(page.getByTestId('chat-answer-text')).toHaveText(result.answer)

  // Requirement 2.4: the panel describes the query that actually ran.
  await page.getByTestId('chat-explainability-toggle').click()
  await expect(page.getByTestId('chat-explainability-metrics')).toHaveText(
    result.explanation!.metrics.map((metric) => metric.replaceAll('_', ' ')).join(' and '),
  )
  await expect(page.getByTestId('chat-explainability-group-by')).toHaveText('carrier')

  // One table row per row the API returned, and collapsed until it is asked for (D16).
  await expect(page.getByTestId('chat-answer-table-row')).toHaveCount(0)
  await page.getByTestId('chat-answer-table-toggle').click()
  await expect(page.getByTestId('chat-answer-table-row')).toHaveCount(result.rows.length)

  // ...and the last of those rows must be readable, not sitting under the composer.
  //
  // Regression gate for a defect the row-count assertion above cannot see: the composer is
  // `sticky bottom-0`, so it floats over the end of the transcript. Every row existed and
  // every count matched while the final carrier was hidden behind the input box - measured
  // at last row y 934-970 against composer y 928-972. Counting elements proves they were
  // rendered; only geometry proves they can be read.
  const lastRow = page.getByTestId('chat-answer-table-row').last()
  await lastRow.scrollIntoViewIfNeeded()
  const lastRowBox = await lastRow.boundingBox()
  const composerBox = await page.getByTestId('chat-composer').boundingBox()
  expect(lastRowBox).not.toBeNull()
  expect(composerBox).not.toBeNull()
  expect(lastRowBox!.y + lastRowBox!.height).toBeLessThanOrEqual(composerBox!.y)

  mkdirSync(EVIDENCE_DIR, { recursive: true })
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '06_chat_answer_screenshot.png'),
    fullPage: true,
  })
})

test('an out-of-scope question renders as a normal answer, not an error', async ({ page }) => {
  await openChat(page)
  const result = await ask(page, "What's the weather in Hong Kong?")

  expect(result.display).toBe('unsupported')
  expect(result.rows).toEqual([])
  expect(result.explanation).toBeNull()

  await expect(page.getByTestId('chat-answer-unsupported')).toBeVisible()
  await expect(page.getByTestId('chat-error')).toHaveCount(0)

  // The refusal sentence appears exactly ONCE.
  //
  // Regression gate for a defect every other assertion here was blind to: `AnswerCard`
  // prints `result.answer` in its header for all six display types, and the refusal body
  // printed it a second time. Both `toBeVisible` and `toHaveText` pass happily when a
  // sentence is on screen twice - it took reading the screenshot to see it. Counting
  // occurrences is what makes it a gate.
  expect(await page.getByText(result.answer, { exact: true }).count()).toBe(1)
  // No chart, no working, no table: there is nothing behind a refusal to show.
  await expect(page.getByTestId('chat-answer-chart')).toHaveCount(0)
  await expect(page.getByTestId('chat-explainability-toggle')).toHaveCount(0)

  mkdirSync(EVIDENCE_DIR, { recursive: true })
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '07_chat_refusal_screenshot.png'),
    fullPage: true,
  })
})

test('the chat prints the same total the dashboard does, digit for digit', async ({
  page,
  request,
}) => {
  const kpis = (await (await request.get('/api/kpis')).json()) as {
    total_orders: { value: number }
  }

  await openChat(page)
  const result = await ask(page, 'How many orders do we have in total?')

  expect(result.display).toBe('stat')
  expect(result.data?.value, 'the chat and /api/kpis are the same number').toBe(
    kpis.total_orders.value,
  )
  // Printed verbatim: if the browser ever locale-formats or re-rounds a figure, this fails.
  await expect(page.getByTestId('chat-answer-stat-value')).toHaveText(
    String(kpis.total_orders.value),
  )
})

test('the sidebar switches between the two screens', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('dashboard')).toBeVisible()

  await page.getByTestId('nav-ask-ai').click()
  await expect(page.getByTestId('chat-page')).toBeVisible()
  await expect(page.getByTestId('chat-empty')).toBeVisible()
  await expect(page.getByTestId('dashboard')).toHaveCount(0)

  await page.getByTestId('nav-dashboard').click()
  await expect(page.getByTestId('dashboard')).toBeVisible()
  await expect(page.getByTestId('chat-page')).toHaveCount(0)
})
