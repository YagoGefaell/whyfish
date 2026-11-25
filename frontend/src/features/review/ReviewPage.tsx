import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { ApiError } from '../../api/client'
import { gamesApi, type GameState } from '../../api/games'
import { playerNames } from './names'
import { ReviewView } from './ReviewView'
import { useAnalysis, type EventSourceFactory } from './useAnalysis'

export function ReviewPage({ eventSourceFactory }: { eventSourceFactory?: EventSourceFactory }) {
  const { id } = useParams()
  const gameId = Number(id)
  if (!Number.isInteger(gameId) || gameId <= 0) {
    return <p className="text-red-600">Partida no válida.</p>
  }
  return <ReviewLoader key={gameId} gameId={gameId} factory={eventSourceFactory} />
}

function ReviewLoader({ gameId, factory }: { gameId: number; factory?: EventSourceFactory }) {
  const [game, setGame] = useState<GameState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { phase, start } = useAnalysis(gameId, factory)
  const location = useLocation()
  const warnings = (location.state as { warnings?: string[] } | null)?.warnings ?? []

  useEffect(() => {
    gamesApi
      .get(gameId)
      .then(setGame)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'No se pudo cargar la partida.')
      })
  }, [gameId])

  if (error) return <p className="text-red-600">{error}</p>
  if (!game) return <p className="text-gray-500">Cargando…</p>
  const names = playerNames(game)
  const canAnalyse = game.source === 'imported' || game.status === 'finished'

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-xl font-semibold">
          Revisión: {names.white} – {names.black}
          {game.result && game.result !== '*' ? ` (${game.result})` : ''}
        </h2>
        {(game.event ?? game.played_date) && (
          <p className="text-sm text-gray-500">
            {[game.event, game.played_date].filter(Boolean).join(' · ')}
          </p>
        )}
        {warnings.map((w) => (
          <p key={w} role="note" className="text-sm text-amber-700">
            {w}
          </p>
        ))}
      </header>
      {phase.kind === 'loading' && <p className="text-gray-500">Comprobando el análisis…</p>}
      {phase.kind === 'none' &&
        (canAnalyse ? (
          <div className="flex flex-col items-start gap-2">
            <p>Esta partida aún no está analizada.</p>
            <button
              type="button"
              onClick={start}
              className="rounded bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800"
            >
              Analizar partida
            </button>
          </div>
        ) : (
          <p>
            Termina la partida para poder analizarla.{' '}
            <Link className="text-blue-700 underline" to={`/play/${String(game.id)}`}>
              Volver a la partida
            </Link>
          </p>
        ))}
      {phase.kind === 'running' && <AnalysisProgress done={phase.done} total={phase.total} />}
      {phase.kind === 'failed' && (
        <div className="flex flex-col items-start gap-2">
          <p role="alert" className="text-red-600">
            El análisis ha fallado: {phase.error}
          </p>
          <button
            type="button"
            onClick={start}
            className="rounded border px-3 py-1 hover:bg-gray-100"
          >
            Reintentar
          </button>
        </div>
      )}
      {phase.kind === 'error' && (
        <p role="alert" className="text-red-600">
          {phase.message}
        </p>
      )}
      {phase.kind === 'ready' && <ReviewView game={game} review={phase.review} />}
    </div>
  )
}

export function AnalysisProgress({ done, total }: { done: number; total: number }) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div className="flex max-w-md flex-col gap-1">
      <p>
        Analizando la partida con Stockfish…{' '}
        {total > 0 ? `${String(done)}/${String(total)} posiciones` : ''}
      </p>
      <div
        role="progressbar"
        aria-label="Progreso del análisis"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="h-3 w-full overflow-hidden rounded bg-gray-200"
      >
        <div
          className="h-full bg-blue-600 transition-all"
          style={{ width: `${String(percent)}%` }}
        />
      </div>
    </div>
  )
}
