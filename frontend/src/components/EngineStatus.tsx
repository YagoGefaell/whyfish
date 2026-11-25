import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResponse } from '../api/health'

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; health: HealthResponse }
  | { kind: 'error'; message: string }

export function EngineStatus() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal)
      .then((health) => {
        setState({ kind: 'loaded', health })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ kind: 'error', message: error instanceof Error ? error.message : 'Error' })
      })
    return () => {
      controller.abort()
    }
  }, [])

  switch (state.kind) {
    case 'loading':
      return <span className="text-gray-500">Comprobando el motor…</span>
    case 'error':
      return (
        <span className="text-red-600">
          No se pudo contactar con el servidor ({state.message}).
        </span>
      )
    case 'loaded': {
      const { engine } = state.health
      return engine.status === 'ok' ? (
        <span className="text-green-700">Motor listo: {engine.name}</span>
      ) : (
        <span className="text-red-600">
          Motor no disponible: {engine.detail ?? 'motivo desconocido'}
        </span>
      )
    }
  }
}
