import { useCallback } from 'react'

import { fetchChart, type ChartResponse, type ChartRoute } from '@/lib/api'
import { useRemoteData, type RemoteData } from '@/hooks/useRemoteData'

/**
 * One chart's rows and echoed params, from one of the three fixed routes (D9).
 *
 * One hook per concern (react rule 7): the page calls it three times rather than a single
 * hook fetching all three, so one slow or failing chart never blanks the other two.
 *
 * `useCallback` keys the loader to the route, which is what makes the underlying effect
 * re-run when - and only when - the route changes.
 */
export function useChart(route: ChartRoute): RemoteData<ChartResponse> {
  const load = useCallback(() => fetchChart(route), [route])
  return useRemoteData(load)
}
