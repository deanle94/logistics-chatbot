import { useCallback, useEffect, useRef, useState } from 'react'

import { newConversationId, streamChat, type ChatResult, type ChatStage } from '@/lib/chatApi'

/**
 * One question and whatever has come back for it so far.
 *
 * `stages` grows while the answer is being worked out and `result` arrives once. Keeping
 * both on the turn rather than in separate lists is what lets the transcript re-render a
 * finished turn without the progress lines reappearing.
 */
export interface ChatTurnState {
  id: string
  question: string
  stages: ChatStage[]
  result: ChatResult | null
  error: string | null
}

/** What the page gets: the transcript, whether a turn is open, and how to ask. */
export interface ChatStream {
  turns: ChatTurnState[]
  pending: boolean
  ask: (question: string) => void
}

/**
 * Drive the chat conversation: post a question, read its frames, update its turn.
 *
 * All the fetch/stream machinery lives here rather than in the page (react rule 7), so
 * `ChatPage` composes components and owns no networking.
 *
 * One conversation id for the lifetime of the page, generated once in a ref. It is the
 * server's checkpoint key, so a reply to a follow-up ("by week") only resolves because the
 * second request carries the same id as the first (agent-design rule 7). Regenerating it
 * per render would silently turn every follow-up into a new, contextless question.
 *
 * The in-flight request is aborted on unmount (rule 8): a stream outliving its component
 * would keep setting state on something that no longer exists.
 */
export function useChatStream(): ChatStream {
  const conversationId = useRef<string>(newConversationId())
  const controller = useRef<AbortController | null>(null)
  const [turns, setTurns] = useState<ChatTurnState[]>([])
  const [pending, setPending] = useState(false)

  useEffect(() => {
    return () => controller.current?.abort()
  }, [])

  const ask = useCallback((question: string) => {
    const trimmed = question.trim()
    if (trimmed.length === 0) return

    // Only a React key for this turn, so the same generator does fine.
    const id = newConversationId()
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort

    // Replace, never mutate (rule 4) - the turn is appended as a new array so the
    // transcript re-renders, and every later update replaces just this turn.
    setTurns((current) => [
      ...current,
      { id, question: trimmed, stages: [], result: null, error: null },
    ])
    setPending(true)

    const update = (change: Partial<ChatTurnState>) => {
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, ...change } : turn)))
    }

    void (async () => {
      try {
        for await (const event of streamChat(
          { question: trimmed, conversationId: conversationId.current },
          abort.signal,
        )) {
          if (event.kind === 'stage') {
            setTurns((current) =>
              current.map((turn) =>
                turn.id === id ? { ...turn, stages: [...turn.stages, event.stage] } : turn,
              ),
            )
          } else if (event.kind === 'result') {
            update({ result: event.result })
          } else {
            update({ error: event.message })
          }
        }
      } catch (error: unknown) {
        // An abort is this component tidying up after itself, not a failure to report.
        if (abort.signal.aborted) return
        update({ error: error instanceof Error ? error.message : 'unknown error' })
      } finally {
        if (!abort.signal.aborted) setPending(false)
      }
    })()
  }, [])

  return { turns, pending, ask }
}
