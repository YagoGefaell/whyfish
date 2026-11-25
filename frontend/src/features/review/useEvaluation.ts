import { useEffect, useState } from 'react'
import { analysisApi, type Evaluation } from '../../api/analysis'

export const EVALUATION_DEBOUNCE_MS = 250

/**
 * Engine evaluation of `fen` after `moves`, for exploring variations. Requests are debounced
 * and the previous one is aborted when the position changes; a result is only shown for the
 * request it belongs to, so moving fast never shows a stale evaluation. `null` = nothing.
 */
export function useEvaluation(target: { fen: string; moves: string[] } | null) {
  const key = target ? `${target.fen}|${target.moves.join(' ')}` : null
  const [result, setResult] = useState<{ key: string; evaluation: Evaluation | null } | null>(null)

  useEffect(() => {
    if (!target || key === null) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      analysisApi
        .evaluate(target.fen, target.moves, controller.signal)
        .then((evaluation) => {
          setResult({ key, evaluation })
        })
        .catch(() => {
          if (!controller.signal.aborted) setResult({ key, evaluation: null })
        })
    }, EVALUATION_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
    // `key` captures target's content; the object identity may change every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const current = key !== null && result?.key === key ? result : null
  return { evaluation: current?.evaluation ?? null, loading: key !== null && current === null }
}
