import { TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { fetchHealth } from '../api/health'

/** Discreet header warning, shown only when the engine (or the server) is not available. */
export function EngineStatus() {
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal)
      .then((health) => {
        const { engine } = health
        setProblem(
          engine.status === 'ok'
            ? null
            : `Motor no disponible: ${engine.detail ?? 'motivo desconocido'}`,
        )
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setProblem(
          `No se pudo contactar con el servidor (${error instanceof Error ? error.message : 'error'}).`,
        )
      })
    return () => {
      controller.abort()
    }
  }, [])

  if (!problem) return null
  return (
    <span
      role="status"
      className="inline-flex items-center gap-1.5 text-sm text-warn"
      title={problem}
    >
      <TriangleAlert size={15} aria-hidden="true" />
      <span className="max-w-[40ch] truncate">{problem}</span>
    </span>
  )
}
