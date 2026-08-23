import { Database, LayoutDashboard, Sparkles, Truck } from 'lucide-react'

/**
 * The 256px left rail of `docs/design/Main.dc.html`: brand, nav, dataset footer.
 *
 * Deliberately plain markup rather than shadcn's `sidebar` component. That component
 * brings a provider, a cookie-persisted open/closed state, a mobile sheet and a keyboard
 * shortcut; this rail has two items, one of which is inert. The machinery would outweigh
 * the feature (CLAUDE.md: do not over-engineer).
 *
 * "Ask AI" is rendered but does nothing - Slice 1 has no AI, it is Slice 2 work - so it is
 * a non-interactive item rather than a button that would lie about being clickable.
 */
export function AppSidebar() {
  return (
    <aside
      className="flex w-64 shrink-0 flex-col border-r bg-sidebar"
      data-testid="app-sidebar"
    >
      <div className="flex h-16 items-center gap-2 border-b px-4">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Truck className="size-[18px]" aria-hidden="true" />
        </div>
        <div className="flex min-w-0 flex-col">
          {/*
            The one h1 on the page. The Slice 0 browser gate asserts on the heading role
            named "Logistics Analytics", and a real heading is what assistive technology
            needs anyway - so the brand mark is a heading, not a styled span.
          */}
          <h1 className="text-sm leading-[18px] font-semibold tracking-tight">
            Logistics Analytics
          </h1>
          <span className="text-xs leading-[15px] text-muted-foreground">AI-powered</span>
        </div>
      </div>

      <nav className="flex grow flex-col gap-1 px-3 py-4" aria-label="Platform">
        <div className="px-2 pb-1 text-xs leading-4 font-medium text-muted-foreground">
          Platform
        </div>
        <div
          className="flex h-8 items-center gap-2 rounded-lg bg-accent px-2 text-sm font-medium"
          aria-current="page"
          data-testid="nav-dashboard"
        >
          <LayoutDashboard className="size-4" aria-hidden="true" />
          <span>Dashboard</span>
        </div>
        <div
          className="flex h-8 items-center gap-2 rounded-lg px-2 text-sm text-muted-foreground"
          data-testid="nav-ask-ai"
        >
          <Sparkles className="size-4" aria-hidden="true" />
          <span>Ask AI</span>
        </div>
      </nav>

      <div className="border-t p-3">
        <div className="flex flex-col gap-1 rounded-lg border bg-card p-3">
          <div className="flex items-center gap-1.5 text-xs leading-4 font-medium">
            <Database className="size-3.5" aria-hidden="true" />
            <span>mock_logistics_data</span>
          </div>
          {/*
            Static copy straight from the design file, not a computed number: the row count
            is a property of the shipped dataset, and inventing a front-end query to
            re-count it would put a definition outside the calculator.
          */}
          <span
            className="text-xs leading-4 text-muted-foreground"
            data-testid="dataset-summary"
          >
            400 rows &middot; read-only
          </span>
        </div>
      </div>
    </aside>
  )
}
