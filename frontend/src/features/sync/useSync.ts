import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { syncApi, type SyncState } from '../../api/sync'

const POLL_MS = 1000

/** Sync state, polled while a sync runs. `onFinished` is called when one ends. */
export function useSync(onFinished?: () => void) {
  const [state, setState] = useState<SyncState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const finished = useRef(onFinished)
  useEffect(() => {
    finished.current = onFinished
  }, [onFinished])
  const running = state?.running ?? false

  useEffect(() => {
    syncApi
      .state()
      .then(setState)
      .catch(() => {
        // The page still works without it.
      })
  }, [])

  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => {
      syncApi
        .state()
        .then((next) => {
          setState(next)
          if (!next.running) finished.current?.()
        })
        .catch(() => {
          // Try again on the next tick.
        })
    }, POLL_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [running])

  const start = useCallback((older = false) => {
    setError(null)
    syncApi
      .start(older)
      .then(setState)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'No se pudo iniciar la sincronización.')
      })
  }, [])

  return { state, error, start }
}

export const PLATFORM_LABEL = { lichess: 'Lichess', chesscom: 'Chess.com' } as const
