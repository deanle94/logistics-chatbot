import type { ChatStat } from '@/lib/chatApi'
import { formatMetricValue, humanizeKey } from '@/lib/metricFormat'

type StatAnswerProps = {
  stat: ChatStat
}

/**
 * Answer type 1 of `docs/design/AnswerTypes.dc.html`: the answer is one number.
 *
 * No chart and no axes - there is nothing to plot. The figure is printed exactly as the
 * backend sent it; this component appends a percent sign where the metric calls for one
 * and adds nothing else, because a browser that rescales a number is a second place a
 * definition lives (architecture Decision 1).
 */
export function StatAnswer({ stat }: StatAnswerProps) {
  return (
    <div className="flex flex-col gap-1 py-4">
      <span
        className="text-5xl leading-none font-semibold tracking-tight tabular-nums"
        data-testid="chat-answer-stat-value"
      >
        {formatMetricValue(stat.metric, stat.value)}
      </span>
      <span className="text-sm text-muted-foreground">{humanizeKey(stat.metric)}</span>
    </div>
  )
}
