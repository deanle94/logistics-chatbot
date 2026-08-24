import { Check, Loader2 } from 'lucide-react'

import type { ChatStage } from '@/lib/chatApi'

type ProgressListProps = {
  stages: ChatStage[]
}

/**
 * What each stage is called in the customer's words rather than the system's.
 *
 * The wire enum is closed (decision D23b) precisely so this mapping can exist: renaming a
 * graph node cannot change what a person reads here, and a stage the browser does not know
 * is simply not rendered instead of leaking an internal name onto the screen.
 */
const STAGE_LABEL: Record<ChatStage, string> = {
  interpreting: 'Understood your question',
  querying: 'Found the right figures to count',
  composing: 'Counting across your orders',
}

/**
 * The "working on it" state of `docs/design/States.dc.html` #2.
 *
 * Every stage but the last is done, so the last one spins and the rest get a tick. That is
 * derived from the array's length rather than stored (react rule 2) - a separate "current
 * stage" field would be a second source of truth that could disagree with the list.
 */
export function ProgressList({ stages }: ProgressListProps) {
  return (
    <ol className="flex flex-col gap-2 py-2" data-testid="chat-progress">
      {stages.map((stage, index) => (
        <li
          // Stages never repeat within a turn, so the stage itself is a stable identity
          // (react rule 5 - never an array index).
          key={stage}
          className="flex items-center gap-2 text-sm text-muted-foreground"
          data-testid="chat-progress-line"
        >
          {index === stages.length - 1 ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Check className="size-3.5 text-primary" aria-hidden="true" />
          )}
          <span>{STAGE_LABEL[stage]}</span>
        </li>
      ))}
    </ol>
  )
}
