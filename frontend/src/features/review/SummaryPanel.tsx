import { Play } from 'lucide-react'
import type { Review } from '../../api/analysis'
import type { Color } from '../../api/games'
import { ClassBadge } from '../../components/ClassBadge'
import { CLASS_ORDER, CLASSIFICATIONS, moveNumber } from './classification'

interface Props {
  review: Review
  names: { white: string; black: string }
  onStart: () => void
  onSelect: (position: number) => void
}

export function ColorDot({ color }: { color: Color }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-3 w-3 rounded-full ring-1 ${
        color === 'white' ? 'bg-eval-white ring-black/30' : 'bg-eval-black ring-white/40'
      }`}
    />
  )
}

export function SummaryPanel({ review, names, onStart, onSelect }: Props) {
  const user: Color = review.perspective
  const byPly = new Map(review.moves.map((m) => [m.ply, m]))
  const userCol = (color: Color) => (color === user ? 'bg-white/[0.06]' : '')
  const accuracy = (a: number | null) => (a === null ? '–' : a.toFixed(1))

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3">
        {(['white', 'black'] as const).map((color) => (
          <div
            key={color}
            data-testid={`accuracy-${color}`}
            className={`rounded-xl p-3 text-center ${color === user ? 'bg-panel-2 ring-1 ring-accent/60' : 'bg-panel-2/50'}`}
          >
            <p className="truncate text-sm text-muted" title={names[color]}>
              {names[color]}
              {color === user && names[color] !== 'Tú' ? ' (tú)' : ''}
            </p>
            <p className="tabular text-3xl font-bold">{accuracy(review[color].accuracy)}</p>
            <p className="text-xs text-muted">precisión</p>
          </div>
        ))}
      </div>

      <table className="tabular w-full text-sm" aria-label="Resumen">
        <thead>
          <tr className="text-xs text-muted">
            <th className="py-1 text-left font-medium">
              <span className="sr-only">Categoría</span>
            </th>
            {(['white', 'black'] as const).map((color) => (
              <th key={color} className={`w-14 py-1 font-medium ${userCol(color)}`}>
                <ColorDot color={color} />
                <span className="sr-only">{names[color]}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {CLASS_ORDER.map((c) => (
            <tr key={c} className="border-b border-line/60 last:border-0">
              <td className="flex items-center gap-2 py-1.5">
                <ClassBadge classification={c} size={20} />
                <span>{CLASSIFICATIONS[c].label}</span>
              </td>
              {(['white', 'black'] as const).map((color) => {
                const n = review[color].counts[c]
                return (
                  <td
                    key={color}
                    className={`w-14 text-center ${userCol(color)} ${n === 0 ? 'text-faint' : 'font-semibold'}`}
                  >
                    {n}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-muted">Momentos clave</h3>
        {review.key_moments.length === 0 ? (
          <p className="text-sm text-muted">Ninguno: ¡partida limpia!</p>
        ) : (
          <ul aria-label="Momentos clave" className="flex flex-col gap-1">
            {review.key_moments.map((ply) => {
              const move = byPly.get(ply)
              if (!move) return null
              return (
                <li key={ply}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(ply + 1)
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-white/5"
                  >
                    <ClassBadge classification={move.classification} size={18} />
                    <span className="tabular font-medium">
                      {moveNumber(ply)} {move.san}
                    </span>
                    <span className="text-muted">{CLASSIFICATIONS[move.classification].label}</span>
                    {move.delta >= 0.5 && (
                      <span className="tabular ml-auto text-muted">−{move.delta.toFixed(0)} %</span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <button type="button" className="btn-primary w-full py-2.5 text-base" onClick={onStart}>
        <Play size={18} /> Empezar revisión
      </button>
    </div>
  )
}
