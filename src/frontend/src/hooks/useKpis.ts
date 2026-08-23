import { fetchKpis, type KpisResponse } from '@/lib/api'
import { useRemoteData, type RemoteData } from '@/hooks/useRemoteData'

/**
 * The five dashboard KPIs from `GET /api/kpis`.
 *
 * `fetchKpis` is a module-level function, so it is already stable and needs no
 * `useCallback` to keep the effect from re-running.
 */
export function useKpis(): RemoteData<KpisResponse> {
  return useRemoteData(fetchKpis)
}
