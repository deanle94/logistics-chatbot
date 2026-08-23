import { fetchHealth, type HealthResponse } from '@/lib/api'
import { useRemoteData, type RemoteData } from '@/hooks/useRemoteData'

/**
 * Backend health for the header indicator.
 *
 * Kept as its own hook so the badge that shows it owns its own state (react rule 6) - the
 * dashboard page never re-renders because a health poll came back.
 */
export function useHealth(): RemoteData<HealthResponse> {
  return useRemoteData(fetchHealth)
}
