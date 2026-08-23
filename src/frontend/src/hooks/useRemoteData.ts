import { useEffect, useState } from 'react'

/**
 * The three states a backend-backed value can be in.
 *
 * A discriminated union rather than `{data, loading, error}`: the compiler then refuses
 * to read `data` before it has been checked, so "rendered before it loaded" is a build
 * error instead of a blank card in the browser.
 */
export type RemoteData<T> =
  | { kind: 'loading' }
  | { kind: 'loaded'; data: T }
  | { kind: 'error'; message: string }

/**
 * Run one backend call and report it as a `RemoteData`.
 *
 * This is the single copy of the fetch/loading/error dance (react rule 7). `load` must be
 * a stable function - a module-level one, or a `useCallback` - because it is the effect's
 * only dependency; an inline arrow would re-fetch on every render.
 *
 * The effect talks to the network, which is the one thing effects are for (rule 3), and it
 * cleans up (rule 8): `active` is flipped on unmount so a late response cannot set state
 * on a component that is gone, including during React's development double-render.
 */
export function useRemoteData<T>(load: () => Promise<T>): RemoteData<T> {
  const [state, setState] = useState<RemoteData<T>>({ kind: 'loading' })

  useEffect(() => {
    let active = true
    setState({ kind: 'loading' })

    load()
      .then((data) => {
        if (active) setState({ kind: 'loaded', data })
      })
      .catch((error: unknown) => {
        if (active) {
          setState({
            kind: 'error',
            message: error instanceof Error ? error.message : 'unknown error',
          })
        }
      })

    return () => {
      active = false
    }
  }, [load])

  return state
}
