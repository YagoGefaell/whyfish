import { useEffect, useState } from 'react'
import { analysisApi, type Explanation } from '../../api/analysis'

/** Explanations already fetched in this session (they never change for an analysed game). */
const cache = new Map<string, Explanation>()

/**
 * Explanation of move `ply` at `level` (null = no move selected). Cached per session; the
 * previous request is aborted when the move or the level changes.
 */
export function useExplanation(gameId: number, ply: number | null, level: 1 | 2) {
  const key = ply === null ? null : `${String(gameId)}:${String(ply)}:${String(level)}`
  const [result, setResult] = useState<{ key: string; explanation: Explanation | null } | null>(
    null,
  )

  useEffect(() => {
    if (key === null || ply === null || cache.has(key)) return
    const controller = new AbortController()
    analysisApi
      .explanation(gameId, ply, level, controller.signal)
      .then((explanation) => {
        cache.set(key, explanation)
        setResult({ key, explanation })
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ key, explanation: null })
      })
    return () => {
      controller.abort()
    }
  }, [key, gameId, ply, level])

  if (key === null) return { explanation: null, loading: false }
  const cached = cache.get(key)
  if (cached) return { explanation: cached, loading: false }
  const current = result?.key === key ? result : null
  return { explanation: current?.explanation ?? null, loading: current === null }
}
