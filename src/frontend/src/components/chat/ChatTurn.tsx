import { AnswerCard } from '@/components/chat/AnswerCard'
import { ProgressList } from '@/components/chat/ProgressList'
import type { ChatTurnState } from '@/hooks/useChatStream'

type ChatTurnProps = {
  turn: ChatTurnState
  onAnswerFollowUp: (option: string) => void
}

/**
 * One exchange: what was asked, and what came back.
 *
 * Exactly one of three things shows at any moment, and which one is derived from the turn
 * rather than tracked separately (react rule 2) - an answer that has arrived is an answer,
 * so the progress lines stop rendering on their own instead of being switched off.
 *
 * A fault is the only thing that renders as an error. A refusal is an answer and gets the
 * ordinary card (decision D23), because the service worked correctly when it declined.
 */
export function ChatTurn({ turn, onAnswerFollowUp }: ChatTurnProps) {
  return (
    <article className="flex flex-col gap-3" data-testid="chat-turn">
      <p className="self-end rounded-2xl bg-accent px-4 py-2 text-sm" data-testid="chat-question">
        {turn.question}
      </p>

      {turn.result === null && turn.error === null && <ProgressList stages={turn.stages} />}

      {turn.error !== null && (
        <p
          className="rounded-xl border border-destructive/40 p-4 text-sm"
          data-testid="chat-error"
        >
          {turn.error}
        </p>
      )}

      {turn.result !== null && (
        <AnswerCard result={turn.result} onAnswerFollowUp={onAnswerFollowUp} />
      )}
    </article>
  )
}
