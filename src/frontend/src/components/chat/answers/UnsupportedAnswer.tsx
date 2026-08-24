/**
 * The polite refusal of `docs/design/States.dc.html` #3, rendered as a normal answer.
 *
 * Deliberately not an error state. Both refusal layers - out of domain, and in domain with
 * an unsupported split - arrive in the same envelope as every other answer (decision D23),
 * so this offers no retry: the question will not succeed on a second attempt, and saying
 * what the assistant *can* answer is more use than a button that does nothing.
 *
 * It takes no `answer` prop on purpose. `AnswerCard` already prints `result.answer` in the
 * header for every one of the six display types, and this body reprinting it put the
 * refusal sentence on screen twice - visible in the first cut of
 * `evidence/07_chat_refusal_screenshot.png`. The body's job is only the part the header
 * cannot carry: what the assistant *can* be asked instead.
 */
export function UnsupportedAnswer() {
  return (
    <div className="flex flex-col gap-3 py-2" data-testid="chat-answer-unsupported">
      <div className="rounded-xl border bg-muted/40 p-4">
        <p className="text-xs font-medium text-muted-foreground">What I can answer</p>
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-4 text-sm text-muted-foreground">
          <li>How many orders there are, and where they got to</li>
          <li>How often deliveries arrive late, and how long they take</li>
          <li>Any of those split by carrier, region, warehouse, category or month</li>
        </ul>
      </div>
    </div>
  )
}
