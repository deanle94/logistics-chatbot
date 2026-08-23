import { ChevronRight, Table2 } from 'lucide-react'

import { BackendStatusBadge } from '@/components/layout/BackendStatusBadge'

/**
 * The 64px header of `docs/design/Main.dc.html`: breadcrumb on the left, badges on the right.
 *
 * "Counted straight from your orders" is the design's promise that no number on this page
 * was written by an AI - every one of them came out of the calculator.
 *
 * The design's settings button is replaced by the live backend indicator: an inert gear
 * would be a control that does nothing, while the indicator earns its place and keeps the
 * Slice 0 browser gate green.
 */
export function AppHeader() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b px-6">
      <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
        <span className="text-muted-foreground">Analytics</span>
        <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">Dashboard</span>
      </nav>

      <div className="flex items-center gap-2">
        <div
          className="inline-flex h-[22px] items-center gap-1.5 rounded-lg border px-2 text-xs font-medium text-muted-foreground"
          data-testid="counted-badge"
        >
          <Table2 className="size-3" aria-hidden="true" />
          Counted straight from your orders
        </div>
        <BackendStatusBadge />
      </div>
    </header>
  )
}
