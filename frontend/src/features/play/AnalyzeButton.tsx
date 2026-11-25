import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { analysisApi } from '../../api/analysis'
import { ApiError } from '../../api/client'
import type { GameSummary } from '../../api/games'

const PRIMARY =
  'rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50'
const SECONDARY = 'rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100'

/** "Analizar partida" (starts the analysis and opens the review) or "Ver revisión". */
export function AnalyzeButton({ game, compact = false }: { game: GameSummary; compact?: boolean }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reviewUrl = `/review/${String(game.id)}`

  if (game.analysis_status === 'done') {
    return (
      <Link className={compact ? 'text-blue-700 hover:underline' : SECONDARY} to={reviewUrl}>
        Ver revisión
      </Link>
    )
  }
  if (game.analysis_status === 'running' || game.analysis_status === 'pending') {
    return (
      <Link className={compact ? 'text-blue-700 hover:underline' : SECONDARY} to={reviewUrl}>
        Analizando…
      </Link>
    )
  }
  const start = () => {
    setBusy(true)
    setError(null)
    analysisApi
      .start(game.id)
      .then(() => navigate(reviewUrl))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'No se pudo iniciar el análisis.')
        setBusy(false)
      })
  }
  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={start}
        disabled={busy}
        className={compact ? 'text-blue-700 hover:underline disabled:opacity-50' : PRIMARY}
      >
        {busy ? 'Iniciando…' : 'Analizar partida'}
      </button>
      {error && (
        <span role="alert" className="text-sm text-red-600">
          {error}
        </span>
      )}
    </span>
  )
}
