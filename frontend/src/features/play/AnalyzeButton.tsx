import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { analysisApi } from '../../api/analysis'
import { ApiError } from '../../api/client'
import type { GameSummary } from '../../api/games'

const PRIMARY = 'btn-primary'
const SECONDARY = 'btn'

/** "Analizar partida" (starts the analysis and opens the review) or "Ver revisión". */
export function AnalyzeButton({ game, compact = false }: { game: GameSummary; compact?: boolean }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reviewUrl = `/review/${String(game.id)}`

  if (game.analysis_status === 'done') {
    return (
      <Link className={compact ? 'text-accent-strong hover:underline' : SECONDARY} to={reviewUrl}>
        Ver revisión
      </Link>
    )
  }
  if (game.analysis_status === 'running' || game.analysis_status === 'pending') {
    return (
      <Link className={compact ? 'text-accent-strong hover:underline' : SECONDARY} to={reviewUrl}>
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
        className={compact ? 'text-accent-strong hover:underline disabled:opacity-50' : PRIMARY}
      >
        {busy ? 'Iniciando…' : 'Analizar partida'}
      </button>
      {error && (
        <span role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
    </span>
  )
}
