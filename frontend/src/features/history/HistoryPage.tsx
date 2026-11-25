import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { gamesApi, type GameSummary } from '../../api/games'
import { COLOR_LABEL, outcomeShortText } from '../play/gameText'

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

  if (error) return <p className="text-red-600">{error}</p>
  if (!games) return <p className="text-gray-500">Cargando…</p>
  if (games.length === 0) {
    return (
      <p>
        Aún no has jugado ninguna partida. <Link to="/">Empieza una</Link>.
      </p>
    )
  }

  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b text-gray-500">
        <tr>
          <th className="py-2">Fecha</th>
          <th>Color</th>
          <th>Nivel</th>
          <th>Resultado</th>
          <th>Jugadas</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {games.map((g) => (
          <tr key={g.id} className="border-b">
            <td className="py-2">{new Date(g.created_at).toLocaleString('es-ES')}</td>
            <td>{COLOR_LABEL[g.player_color]}</td>
            <td>{g.bot_level_label}</td>
            <td>{outcomeShortText(g.result, g.player_color)}</td>
            <td>{Math.ceil(g.move_count / 2)}</td>
            <td>
              <Link className="text-blue-700 hover:underline" to={`/play/${String(g.id)}`}>
                {g.result === null ? 'Continuar' : 'Ver'}
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
