import { Flame, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { trainingApi, type TrainingFilter, type TrainingSession } from '../../api/training'
import { Exercise } from './Exercise'
import { filterLabel } from './labels'

function toFilter(params: URLSearchParams): TrainingFilter {
  const filter: TrainingFilter = {}
  const kind = params.get('error_kind')
  if (kind) filter.error_kind = kind
  const phase = params.get('phase')
  if (phase) filter.phase = phase
  if (params.get('low_time') === 'true') filter.low_time = true
  return filter
}

/** Entrenar (phase 6c): the daily session, or one filtered from a weak point. */
export function TrainPage() {
  const [params] = useSearchParams()
  const query = params.toString()
  // A different filter is a different session: start from scratch.
  return <TrainSession key={query} query={query} />
}

function TrainSession({ query }: { query: string }) {
  const [session, setSession] = useState<TrainingSession | null>(null)
  const [shown, setShown] = useState<number | null>(null) // position on screen
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    trainingApi
      .session(toFilter(new URLSearchParams(query)))
      .then((s) => {
        setSession(s)
        setShown(s.current)
      })
      .catch(() => {
        setError('No se pudo preparar la sesión.')
      })
  }, [query])

  if (error) return <p className="text-danger">{error}</p>
  if (!session) return <p className="text-muted">Preparando la sesión…</p>

  const total = session.positions.length
  const label = filterLabel(session.filter)
  const current = shown !== null ? session.positions[shown] : undefined

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 className="text-xl font-semibold">Entrenar</h2>
        {total > 0 && (
          <span className="tabular text-sm text-muted" aria-label="Progreso">
            {Math.min(session.answered + (current?.state === 'pending' ? 1 : 0), total)} / {total}
            {' · '}
            {session.correct} aciertos
          </span>
        )}
        <span className="inline-flex items-center gap-1 text-sm" aria-label="Racha">
          <Flame size={16} className="text-heat" /> Racha: {session.streak}{' '}
          {session.streak === 1 ? 'día' : 'días'}
        </span>
        {label && (
          <span className="ml-auto inline-flex items-center gap-2 rounded-lg bg-panel-2 px-2.5 py-1 text-sm">
            Entrenando: {label}
            <Link to="/train" aria-label="Quitar filtro" className="text-muted hover:text-fg">
              <X size={14} />
            </Link>
          </span>
        )}
      </div>

      {total === 0 ? (
        <div className="panel flex flex-col gap-2 p-5">
          <p>
            {label ? 'No hay ejercicios de este tipo pendientes.' : 'No hay ejercicios para hoy.'}
          </p>
          <p className="text-sm text-muted">
            Los ejercicios salen de tus errores (?, ?? y ✗) en partidas analizadas.{' '}
            {session.counts.learned ? `${String(session.counts.learned)} aprendidos. ` : ''}
            Fuera: {session.counts.decided} con la partida ya decidida, {session.counts.unclear} sin
            una solución clara
            {session.counts.bullet ? `, ${String(session.counts.bullet)} de bala` : ''}.
          </p>
          <Link className="text-accent-strong underline" to="/games">
            Ir al Historial
          </Link>
        </div>
      ) : current ? (
        <Exercise
          key={`${String(session.id)}-${String(current.position)}`}
          sessionId={session.id}
          position={current.position}
          itemId={current.item_id}
          onAnswered={(attempt) => {
            setSession(attempt.session)
          }}
          onNext={() => {
            setShown(session.current)
          }}
        />
      ) : (
        <div role="status" aria-label="Sesión terminada" className="panel flex flex-col gap-2 p-5">
          <h3 className="text-lg font-semibold">
            Sesión terminada: {session.correct} de {total} a la primera
          </h3>
          <p className="text-sm text-muted">
            {session.daily
              ? 'Vuelve mañana: los ejercicios fallados volverán pronto y los acertados, cada vez más tarde.'
              : 'Puedes volver a la sesión diaria cuando quieras.'}
          </p>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link className="text-accent-strong underline" to="/stats">
              Ver tus estadísticas
            </Link>
            {!session.daily && (
              <Link className="text-accent-strong underline" to="/train">
                Sesión diaria
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
