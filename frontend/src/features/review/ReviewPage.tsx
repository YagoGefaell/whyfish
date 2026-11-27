import { useEffect, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import { ApiError } from '../../api/client'
import { gamesApi, type GameState } from '../../api/games'
import { playerNames } from './names'
import { ReviewView } from './ReviewView'
import { useAnalysis, type AnalysisPhase, type EventSourceFactory } from './useAnalysis'

export function ReviewPage({ eventSourceFactory }: { eventSourceFactory?: EventSourceFactory }) {
  const { id } = useParams()
  const gameId = Number(id)
  if (!Number.isInteger(gameId) || gameId <= 0) {
    return <p className="text-danger">Partida no válida.</p>
  }
  return <ReviewLoader key={gameId} gameId={gameId} factory={eventSourceFactory} />
}

function ReviewLoader({ gameId, factory }: { gameId: number; factory?: EventSourceFactory }) {
  const [game, setGame] = useState<GameState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { phase, start } = useAnalysis(gameId, factory)
  const location = useLocation()
  const warnings = (location.state as { warnings?: string[] } | null)?.warnings ?? []
  // ?ply=N (0-based): open on that move, e.g. from the statistics.
  const [params] = useSearchParams()
  const plyParam = params.get('ply')
  const ply = plyParam !== null && /^\d+$/.test(plyParam) ? Number(plyParam) : null

  useEffect(() => {
    gamesApi
      .get(gameId)
      .then(setGame)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'No se pudo cargar la partida.')
      })
  }, [gameId])

  if (error) return <p className="text-danger">{error}</p>
  if (!game) return <p className="text-muted">Cargando…</p>
  const names = playerNames(game)
  const opening = phase.kind === 'ready' ? phase.review.opening : null
  const meta = [
    game.event,
    game.played_date,
    game.result && game.result !== '*' ? game.result : null,
    opening ? `${opening.eco} ${opening.name}` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="flex flex-col">
      {/* The players' names are on the strips around the board. */}
      <h2 className="sr-only">
        Revisión: {names.white} contra {names.black}
      </h2>
      <ReviewView
        key={ply ?? 'start'}
        game={game}
        initialPly={ply}
        review={phase.kind === 'ready' ? phase.review : null}
        status={<AnalysisStatus phase={phase} game={game} onStart={start} />}
        meta={
          meta || warnings.length > 0 ? (
            <>
              {meta}
              {warnings.map((w) => (
                <p key={w} role="note" className="text-[#f7c631]">
                  {w}
                </p>
              ))}
            </>
          ) : null
        }
      />
    </div>
  )
}

function AnalysisStatus({
  phase,
  game,
  onStart,
}: {
  phase: AnalysisPhase
  game: GameState
  onStart: () => void
}) {
  const canAnalyse = game.source === 'imported' || game.status === 'finished'
  switch (phase.kind) {
    case 'loading':
      return <p className="text-muted">Comprobando el análisis…</p>
    case 'none':
      return canAnalyse ? (
        <div className="flex flex-col items-start gap-3">
          <p>Esta partida aún no está analizada.</p>
          <button type="button" onClick={onStart} className="btn-primary">
            Analizar partida
          </button>
        </div>
      ) : (
        <p>
          Termina la partida para poder analizarla.{' '}
          <Link className="text-accent-strong underline" to={`/play/${String(game.id)}`}>
            Volver a la partida
          </Link>
        </p>
      )
    case 'running':
      return <AnalysisProgress done={phase.done} total={phase.total} />
    case 'failed':
      return (
        <div className="flex flex-col items-start gap-3">
          <p role="alert" className="text-danger">
            El análisis ha fallado: {phase.error}
          </p>
          <button type="button" onClick={onStart} className="btn">
            Reintentar
          </button>
        </div>
      )
    case 'error':
      return (
        <p role="alert" className="text-danger">
          {phase.message}
        </p>
      )
    case 'ready':
      return null
  }
}

export function AnalysisProgress({ done, total }: { done: number; total: number }) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div className="flex flex-col gap-2">
      <p className="font-medium">Analizando la partida…</p>
      <div
        role="progressbar"
        aria-label="Progreso del análisis"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="h-2.5 w-full overflow-hidden rounded-full bg-panel-2"
      >
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${String(percent)}%` }}
        />
      </div>
      <p className="tabular text-sm text-muted">
        {total > 0 ? `${String(done)} de ${String(total)} posiciones` : 'Preparando…'}
      </p>
    </div>
  )
}
