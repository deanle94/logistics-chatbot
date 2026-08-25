import type { ChartParams, ChartRow } from '@/lib/api'

/**
 * The chat wire contract, and the reader that turns `POST /api/chat` into frames.
 *
 * Not axios, and not `EventSource`. The stream is Server-Sent Events over a POST, which
 * `EventSource` cannot issue at all, and axios has no streaming response in the browser.
 * `fetch` + `ReadableStream` is the only combination that does both, and it is built in -
 * so the dashboard keeps axios (S0.6 checks the manifest) and this file adds no dependency.
 */

/** The advisory progress stages, as a closed set (decision D23b; `forecasting` is the
 * Slice 3 hand-extension of spec review Q3). */
export type ChatStage = 'interpreting' | 'querying' | 'forecasting' | 'composing'

/**
 * How an answer is drawn. The backend decides this from the parameters it ran, never the
 * browser and never the model - a chart chosen by a model can be one the data cannot carry.
 */
export type ChatDisplay =
  | 'stat'
  | 'line'
  | 'bar'
  | 'stacked'
  | 'unsupported'
  | 'follow_up'
  | 'forecast_line'

/** The single figure a stat answer prints. */
export interface ChatStat {
  metric: string
  value: number
}

/**
 * The structured question asked when one required parameter is genuinely missing.
 *
 * `options` are rendered as chips. `question` is guaranteed digit-free by the backend's
 * validator, which is what stops a number appearing before any tool has run.
 */
export interface ChatFollowUp {
  missing_info: string
  question: string
  options: string[]
}

/**
 * The typed forecast block of a `forecast_line` answer (Slice 3).
 *
 * Typed rather than fished out of prose: the card renders the recommendation and the
 * methodology from these fields, and every digit in them came from the calculator.
 */
export interface ChatForecast {
  sku: string
  horizon: number
  window: number
  total: number
  recommended_stock: number
  buffer_pct: number
  methodology: string
}

/**
 * One complete answer. Every legal outcome is this shape, refusals and follow-ups included,
 * so the interface has one card to render rather than three.
 *
 * `explanation` is the dashboard's `ChartParams` plus `row_count`, which is why the chat
 * reuses `ChartDataTable` unchanged.
 */
export interface ChatResult {
  answer: string
  display: ChatDisplay
  data: ChatStat | null
  rows: ChartRow[]
  explanation: (ChartParams & { row_count: number }) | null
  follow_up: ChatFollowUp | null
  forecast: ChatForecast | null
}

/** What the reader hands back as the stream runs. */
export type ChatEvent =
  | { kind: 'stage'; stage: ChatStage }
  | { kind: 'result'; result: ChatResult }
  | { kind: 'error'; message: string }

/** What the caller supplies per turn. `conversationId` becomes the server's thread id. */
export interface ChatRequest {
  question: string
  conversationId: string
}

/**
 * An identifier the client owns, so the server route can stay stateless.
 *
 * `crypto.randomUUID` only exists in a secure context, which localhost is and a bare LAN
 * address is not. The fallback is not cryptographic and does not need to be: this value is
 * a conversation key inside one browser tab, never a secret and never an authorisation.
 */
export function newConversationId(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `c-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/**
 * Post one question and yield each frame as it arrives.
 *
 * An async generator rather than a callback: the caller then reads the stream with a plain
 * `for await`, and cancelling is `break` plus the abort signal instead of a subscription to
 * unwind. The signal is what `useChatStream` uses to make its effect clean up (react rule 8).
 */
export async function* streamChat(
  request: ChatRequest,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: request.question,
      conversation_id: request.conversationId,
    }),
    signal,
  })

  if (!response.ok || response.body === null) {
    throw new Error(`the service answered ${response.status}`)
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffered = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffered += value

      // A frame ends at a blank line, and a chunk can split one in half - so only whole
      // frames are parsed here and the remainder stays buffered for the next chunk.
      const blocks = buffered.split('\n\n')
      buffered = blocks.pop() ?? ''
      for (const block of blocks) {
        const event = parseFrame(block)
        if (event !== null) yield event
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** Turn one raw SSE block into an event, or `null` for a frame nobody needs to act on. */
function parseFrame(block: string): ChatEvent | null {
  const fields = new Map<string, string>()
  for (const line of block.split('\n')) {
    const separator = line.indexOf(':')
    if (separator > 0) fields.set(line.slice(0, separator).trim(), line.slice(separator + 1).trim())
  }

  const event = fields.get('event')
  const payload = fields.get('data')
  if (event === undefined || payload === undefined) return null

  if (event === 'stage') {
    return { kind: 'stage', stage: (JSON.parse(payload) as { stage: ChatStage }).stage }
  }
  if (event === 'result') {
    return { kind: 'result', result: JSON.parse(payload) as ChatResult }
  }
  if (event === 'error') {
    return { kind: 'error', message: (JSON.parse(payload) as { message: string }).message }
  }
  return null
}
