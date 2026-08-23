import { ChevronDown } from 'lucide-react'

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ChartParams, ChartRow } from '@/lib/api'

type ChartDataTableProps = {
  testId: string
  rows: ChartRow[]
  params: ChartParams
}

/**
 * Turn a wire key such as `delivery_time` into the words a human reads.
 *
 * Presentation only - it renames nothing and computes nothing, so no definition leaks out
 * of the calculator.
 */
function humanize(key: string): string {
  return key.replaceAll('_', ' ')
}

/**
 * Print one cell exactly as the API sent it.
 *
 * `null` is a real answer - a carrier with no finished orders has no delay rate - and it
 * is shown as a dash rather than silently becoming `0`, which would sort as "perfect".
 */
function cellText(value: string | number | null | undefined): string {
  return value === null || value === undefined ? '—' : String(value)
}

/**
 * The data-table toggle that sits under every chart (decision D16, requirement 2.3/2.4).
 *
 * Collapsed by default: it is the "show your work" drawer, not the main content, and
 * expanding it pushes the page down - the cost D16 accepted.
 *
 * The columns are named by `params.metrics`, not by anything hard-coded here. That is the
 * whole point of the echoed params: the backend says which keys in a row are metrics, so
 * this table renders whatever the query actually asked for, and Slice 2's chat can reuse
 * it unchanged for questions nobody has written down yet.
 */
export function ChartDataTable({ testId, rows, params }: ChartDataTableProps) {
  const filterEntries = Object.entries(params.filters)

  return (
    <Collapsible data-testid={`${testId}-table-collapsible`}>
      <CollapsibleTrigger
        className="group flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-accent"
        data-testid={`${testId}-table-toggle`}
      >
        <span>
          Show data table &middot; {rows.length} {rows.length === 1 ? 'row' : 'rows'}
        </span>
        <ChevronDown
          className="size-4 transition-transform group-data-[state=open]:rotate-180"
          aria-hidden="true"
        />
      </CollapsibleTrigger>

      <CollapsibleContent data-testid={`${testId}-table-content`}>
        <p
          className="px-3 pt-3 text-xs text-muted-foreground"
          data-testid={`${testId}-table-params`}
        >
          {params.metrics.map(humanize).join(', ')} &middot; grouped by{' '}
          {humanize(params.group_by)} &middot;{' '}
          {filterEntries.length === 0
            ? 'no filters'
            : filterEntries.map(([name, value]) => `${humanize(name)} = ${value}`).join(', ')}
        </p>

        {/*
          No height cap: decision D16 already accepted that expanding pushes the page down,
          and capping it would hide rows from the very drawer whose job is to show all of
          them. `overflow-x-auto` still keeps a wide table from widening the card.
        */}
        <div className="mt-2 overflow-x-auto rounded-lg border">
          <Table data-testid={`${testId}-table`}>
            <TableHeader>
              <TableRow>
                <TableHead>{humanize(params.group_by)}</TableHead>
                {params.metrics.map((metric) => (
                  <TableHead key={metric} className="text-right">
                    {humanize(metric)}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                // The group key is the row's identity, so reordering never reuses the
                // wrong DOM node (react rule 5 - never an array index).
                <TableRow key={row.group} data-testid={`${testId}-table-row`}>
                  <TableCell className="font-medium">{row.group}</TableCell>
                  {params.metrics.map((metric) => (
                    <TableCell key={metric} className="text-right tabular-nums">
                      {cellText(row[metric])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
