import { KpiCard } from '@/components/dashboard/KpiCard'
import type { KpisResponse } from '@/lib/api'
import type { RemoteData } from '@/hooks/useRemoteData'

type KpiRowProps = {
  state: RemoteData<KpisResponse>
}

/**
 * The five cards, their labels and their captions - the design's copy, in the design's order.
 *
 * Labels and captions are static text from `docs/design/Main.dc.html`; only the numbers come
 * from the API. The captions that mention counts ("of 359 finished", "370 orders") stay
 * static on purpose: recomputing them in the browser would mean the front-end deciding what
 * "finished" means, and every business definition belongs in `calculator/` (architecture
 * Decision 1).
 *
 * `field` is `keyof KpisResponse`, so renaming a KPI on the wire is a compile error here.
 */
const KPI_CARDS: ReadonlyArray<{
  field: keyof KpisResponse
  label: string
  caption: string
  emphasis: 'default' | 'destructive'
}> = [
  {
    field: 'total_orders',
    label: 'Total orders',
    caption: 'Every order on record',
    emphasis: 'default',
  },
  {
    field: 'delivered_orders',
    label: 'Delivered',
    caption: 'Arrived successfully',
    emphasis: 'default',
  },
  {
    field: 'delayed_orders',
    label: 'Delayed',
    caption: 'Arrived late',
    emphasis: 'destructive',
  },
  {
    field: 'on_time_rate',
    label: 'On-time rate',
    caption: '304 on time of 359 finished',
    emphasis: 'default',
  },
  {
    field: 'average_delivery_time',
    label: 'Avg delivery time',
    caption: 'Across 370 orders with dates',
    emphasis: 'default',
  },
]

/**
 * The KPI row: five cards fed by one `/api/kpis` call.
 *
 * The cards are always mounted, so the layout does not jump when the response lands; each
 * one shows a dash until there is a number to show.
 */
export function KpiRow({ state }: KpiRowProps) {
  // Derived, never stored (react rule 2): there is one source of truth, the request state.
  const kpis = state.kind === 'loaded' ? state.data : null

  return (
    <section aria-label="Key performance indicators" data-testid="kpi-row">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        {KPI_CARDS.map((card) => (
          <KpiCard
            key={card.field}
            testId={`kpi-${card.field}`}
            label={card.label}
            caption={card.caption}
            kpi={kpis === null ? null : kpis[card.field]}
            emphasis={card.emphasis}
          />
        ))}
      </div>
      {state.kind === 'error' && (
        <p className="mt-2 text-xs text-destructive" data-testid="kpi-row-error">
          Could not load the KPIs: {state.message}
        </p>
      )}
    </section>
  )
}
