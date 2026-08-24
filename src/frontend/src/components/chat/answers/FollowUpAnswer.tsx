import { Button } from '@/components/ui/button'
import type { ChatFollowUp } from '@/lib/chatApi'

type FollowUpAnswerProps = {
  followUp: ChatFollowUp
  onAnswer: (option: string) => void
}

/**
 * The structured question the assistant asks when one parameter is genuinely missing.
 *
 * A follow-up ends the turn (agent-design rule 7): the reply goes back through the whole
 * graph as a new question, resolved against the conversation the checkpointer kept. That is
 * why a chip simply asks it - there is no half-finished request sitting here waiting to be
 * completed.
 *
 * `question` carries no digit, guaranteed by a validator rather than by a prompt: no tool
 * has run yet, so there is nothing a number here could be checked against.
 */
export function FollowUpAnswer({ followUp, onAnswer }: FollowUpAnswerProps) {
  return (
    <div className="flex flex-col gap-3 py-2" data-testid="chat-answer-follow-up">
      <p className="text-sm">{followUp.question}</p>
      <div className="flex flex-wrap gap-2">
        {followUp.options.map((option) => (
          <Button
            key={option}
            variant="outline"
            size="sm"
            className="rounded-full"
            onClick={() => onAnswer(option)}
            data-testid="chat-follow-up-option"
          >
            {option}
          </Button>
        ))}
      </div>
    </div>
  )
}
