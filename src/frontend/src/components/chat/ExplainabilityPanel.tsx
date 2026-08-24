import { ChevronDown } from 'lucide-react'

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { ChartParams } from '@/lib/api'
import { humanizeKey } from '@/lib/metricFormat'

type ExplainabilityPanelProps = {
  explanation: ChartParams & { row_count: number }
}

/**
 * "Show the working" - requirement 2.4, drawn from `docs/design/Explainability.dc.html`.
 *
 * Every line here is the backend's echoed parameters, never a description written in the
 * browser. That is the whole point: the panel has to describe the query that actually ran,
 * so if the model had asked for something else this text would say so.
 *
 * Collapsed by default, like the dashboard's data table (decision D16): it is the evidence
 * drawer, not the answer.
 */
export function ExplainabilityPanel({ explanation }: ExplainabilityPanelProps) {
  const filters = Object.entries(explanation.filters)

  return (
    <Collapsible>
      <CollapsibleTrigger
        className="group flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-accent"
        data-testid="chat-explainability-toggle"
      >
        <span>Show the working</span>
        <ChevronDown
          className="size-4 transition-transform group-data-[state=open]:rotate-180"
          aria-hidden="true"
        />
      </CollapsibleTrigger>

      <CollapsibleContent
        className="flex flex-col gap-2 px-3 pt-2 text-xs"
        data-testid="chat-explainability"
      >
        <p>
          <span className="text-muted-foreground">Figure measured: </span>
          <span className="font-medium" data-testid="chat-explainability-metrics">
            {explanation.metrics.map(humanizeKey).join(' and ')}
          </span>
        </p>
        <p>
          <span className="text-muted-foreground">Split by: </span>
          <span className="font-medium" data-testid="chat-explainability-group-by">
            {humanizeKey(explanation.group_by)}
          </span>
        </p>
        <p>
          <span className="text-muted-foreground">Filters used: </span>
          <span className="font-medium" data-testid="chat-explainability-filters">
            {filters.length === 0
              ? 'none - every order on record'
              : filters.map(([name, value]) => `${humanizeKey(name)} = ${value}`).join(', ')}
          </span>
        </p>
        <p>
          <span className="text-muted-foreground">Ordered by: </span>
          <span className="font-medium">{humanizeKey(explanation.order)}</span>
        </p>
      </CollapsibleContent>
    </Collapsible>
  )
}
