import { ExplainabilityPanel } from '@/components/chat/ExplainabilityPanel'
import { BarAnswer } from '@/components/chat/answers/BarAnswer'
import { FollowUpAnswer } from '@/components/chat/answers/FollowUpAnswer'
import { LineAnswer } from '@/components/chat/answers/LineAnswer'
import { StackedAnswer } from '@/components/chat/answers/StackedAnswer'
import { StatAnswer } from '@/components/chat/answers/StatAnswer'
import { UnsupportedAnswer } from '@/components/chat/answers/UnsupportedAnswer'
import { ChartDataTable } from '@/components/dashboard/ChartDataTable'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import type { ChatResult } from '@/lib/chatApi'
import { humanizeKey } from '@/lib/metricFormat'

type AnswerCardProps = {
  result: ChatResult
  onAnswerFollowUp: (option: string) => void
}

/** The badge in the card header, in the words `docs/design/AnswerTypes.dc.html` uses. */
const DISPLAY_LABEL: Record<ChatResult['display'], string> = {
  stat: 'Single figure',
  line: 'Over time',
  bar: 'Comparison',
  stacked: 'Two series',
  unsupported: 'Not available',
  follow_up: 'Needs one detail',
}

/**
 * The one card every answer sits in: header, body, footer.
 *
 * `docs/design/AnswerTypes.dc.html` states the rule this component exists to keep - build
 * the shell once and the six answer types become six body components. Only the body swaps
 * on `display`; the frame, the badge and the footer are identical for all six, which is
 * what makes a refusal render as a normal answer instead of as a special case.
 *
 * The table and the explainability panel are both built from the echoed parameters, so an
 * answer to a question nobody wrote down in advance still explains itself. `ChartDataTable`
 * is the dashboard's, reused unchanged: its columns are named by `params.metrics`, which is
 * exactly what the chat's explanation carries.
 */
export function AnswerCard({ result, onAnswerFollowUp }: AnswerCardProps) {
  const explanation = result.explanation

  return (
    <Card className="gap-4 overflow-hidden rounded-xl py-0" data-testid="chat-answer">
      <CardHeader className="gap-1 px-6 pt-5">
        <div className="flex items-start justify-between gap-4">
          <p className="text-sm leading-6" data-testid="chat-answer-text">
            {result.answer}
          </p>
          <div
            className="inline-flex h-[22px] shrink-0 items-center rounded-lg border px-2 text-xs font-medium text-muted-foreground"
            data-testid="chat-answer-type-badge"
          >
            {DISPLAY_LABEL[result.display]}
          </div>
        </div>
        {explanation !== null && (
          <p className="text-xs text-muted-foreground" data-testid="chat-answer-subtitle">
            {explanation.metrics.map(humanizeKey).join(' and ')} &middot;{' '}
            {explanation.row_count} {explanation.row_count === 1 ? 'row' : 'rows'} counted
          </p>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-3 px-6">
        {result.display === 'stat' && result.data !== null && <StatAnswer stat={result.data} />}
        {result.display === 'line' && explanation !== null && (
          <LineAnswer rows={result.rows} metric={explanation.metrics[0]} />
        )}
        {result.display === 'bar' && explanation !== null && (
          <BarAnswer rows={result.rows} metric={explanation.metrics[0]} />
        )}
        {result.display === 'stacked' && explanation !== null && (
          <StackedAnswer rows={result.rows} metrics={explanation.metrics} />
        )}
        {result.display === 'unsupported' && <UnsupportedAnswer />}
        {result.display === 'follow_up' && result.follow_up !== null && (
          <FollowUpAnswer followUp={result.follow_up} onAnswer={onAnswerFollowUp} />
        )}
      </CardContent>

      {explanation !== null && (
        <div className="flex flex-col gap-1 border-t bg-muted/40 px-3 py-2">
          <ExplainabilityPanel explanation={explanation} />
          {/*
            A stat has nothing to tabulate - one figure, already printed above - so the
            drawer is dropped for it, exactly as AnswerTypes.dc.html specifies.
          */}
          {result.display !== 'stat' && (
            <ChartDataTable testId="chat-answer" rows={result.rows} params={explanation} />
          )}
        </div>
      )}
    </Card>
  )
}
