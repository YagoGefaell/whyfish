import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { gamesApi, type GameSummary } from '../../api/games'
import { AnalyzeButton } from '../play/AnalyzeButton'
import { COLOR_LABEL, outcomeShortText } from '../play/gameText'

function title(g: GameSummary): string {
  if (g.source === 'imported') {
    return `${g.white_name ?? 'Blancas'} – ${g.black_name ?? 'Negras'}`
  }
  return `vs Stockfish (${g.bot_level_label ?? '?'})`
}

export function HistoryPage() {
  const [games, setGames] = useState<GameSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    gamesApi
      .list()
      .then(setGames)
      .catch(() => {
        setError('No se pudo cargar el historial.')
      })
  }, [])

  if (error) return <p className="text-danger">{error}</p>
  if (!games) return <p className="text-muted">Cargando…</p>
  if (games.length === 0) {
    return (
      <p>
        Aún no hay partidas. <Link to="/">Juega una</Link> o{' '}
        <Link to="/import">importa un PGN</Link>.
      </p>
    )
  }

  return (
    <div className="panel overflow-x-auto p-2">
      <h2 className="px-3 pt-2 pb-3 text-lg font-semibold">Historial</h2>
      <table className="w-full text-left text-sm">
        <thead className="border-b border-line text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">Fecha</th>
            <th>Partida</th>
            <th>Tu color</th>
            <th>Resultado</th>
            <th>Jugadas</th>
            <th>Revisión</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {games.map((g) => {
            const ongoing = g.result === null
            return (
              <tr key={g.id} className="border-b border-line">
                <td className="px-3 py-2.5">{new Date(g.created_at).toLocaleString('es-ES')}</td>
                <td>
                  {title(g)}
                  {g.source === 'imported' && (
                    <span className="ml-2 rounded-md bg-panel-2 px-1.5 py-0.5 text-xs text-muted">
                      importada
                    </span>
                  )}
                </td>
                <td>{COLOR_LABEL[g.player_color]}</td>
                <td>{outcomeShortText(g.result, g.player_color)}</td>
                <td>{Math.ceil(g.move_count / 2)}</td>
                <td>
                  {ongoing ? (
                    <span className="text-muted">—</span>
                  ) : (
                    <AnalyzeButton game={g} compact />
                  )}
                </td>
                <td>
                  {g.source === 'played' && (
                    <Link
                      className="text-accent-strong hover:underline"
                      to={`/play/${String(g.id)}`}
                    >
                      {ongoing ? 'Continuar' : 'Ver partida'}
                    </Link>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
