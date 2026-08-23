import { ChevronRight } from 'lucide-react'

/**
 * The 64px header of `docs/design/Main.dc.html`: the breadcrumb, and nothing else.
 *
 * The design also draws a "Counted straight from your orders" badge and a settings button,
 * and Slice 0 put a live backend-health indicator here. All three are gone at the tech
 * lead's request (decision D19a) - the badge was a claim the numbers already make, and the
 * health indicator was operator telemetry on a manager's dashboard.
 */
export function AppHeader() {
  return (
    <header className="flex h-16 shrink-0 items-center border-b px-6">
      <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
        <span className="text-muted-foreground">Analytics</span>
        <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">Dashboard</span>
      </nav>
    </header>
  )
}
