import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResponse } from './api/health'

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; health: HealthResponse }
  | { kind: 'error'; message: string }

export default function App() {
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

  return (
    <main className="mx-auto max-w-xl p-8 font-sans">
      <h1 className="mb-4 text-3xl font-bold">whyfish</h1>
      <EngineStatus state={state} />
    </main>
  )
}

function EngineStatus({ state }: { state: State }) {
  switch (state.kind) {
    case 'loading':
      return <p className="text-gray-500">Comprobando el motor…</p>
    case 'error':
      return <p className="text-red-600">No se pudo contactar con el servidor ({state.message}).</p>
    case 'loaded': {
      const { engine } = state.health
      return engine.status === 'ok' ? (
        <p className="text-green-700">Motor listo: {engine.name}</p>
      ) : (
        <p className="text-red-600">Motor no disponible: {engine.detail ?? 'motivo desconocido'}</p>
      )
    }
  }
}
