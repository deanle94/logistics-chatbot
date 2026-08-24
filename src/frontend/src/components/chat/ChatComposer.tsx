import { useState, type FormEvent } from 'react'
import { SendHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/button'

type ChatComposerProps = {
  disabled: boolean
  onSubmit: (question: string) => void
}

/**
 * The question box of `docs/design/Chat.dc.html`.
 *
 * It owns the draft and nothing else (react rule 6): lifting the text into the page would
 * re-render the whole transcript on every keystroke, for a value no other component reads.
 *
 * A real `<form>` rather than a click handler, so Enter submits the way a person expects
 * and the browser handles the empty case before anything else does.
 */
export function ChatComposer({ disabled, onSubmit }: ChatComposerProps) {
  const [draft, setDraft] = useState('')

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (draft.trim().length === 0) return
    onSubmit(draft)
    setDraft('')
  }

  return (
    <form className="flex items-center gap-2" onSubmit={handleSubmit} data-testid="chat-composer">
      <input
        className="h-11 grow rounded-xl border bg-card px-4 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-60"
        placeholder="Ask about deliveries, carriers, delays or demand&hellip;"
        aria-label="Ask a question about your orders"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        data-testid="chat-input"
      />
      <Button
        type="submit"
        className="h-11 rounded-xl"
        disabled={disabled || draft.trim().length === 0}
        data-testid="chat-submit"
      >
        <SendHorizontal className="size-4" aria-hidden="true" />
        Ask
      </Button>
    </form>
  )
}
