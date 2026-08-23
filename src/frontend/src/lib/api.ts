import axios from 'axios'

/**
 * Shape of `GET /health` as served by the FastAPI backend.
 */
export interface HealthResponse {
  status: 'ok' | 'degraded'
  database: 'reachable' | 'unreachable'
}

/**
 * All backend calls go through a relative `/api` path rather than an absolute URL.
 *
 * nginx proxies `/api` to the backend, so browser and API share one origin: the same
 * bundle works in the container, behind a public URL, and in the dev server without a
 * rebuild, and CORS never enters the picture.
 */
export const api = axios.create({
  baseURL: '/api',
  timeout: 10_000,
})

/**
 * Fetch backend health.
 *
 * A 503 is a valid answer, not a transport failure - the backend returns it when the
 * database is unreachable - so it is unwrapped rather than thrown.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>('/health', {
    validateStatus: (status) => status === 200 || status === 503,
  })
  return response.data
}
