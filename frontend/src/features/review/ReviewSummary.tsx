import type { Review } from '../../api/analysis'
import { CLASS_ORDER, CLASSIFICATIONS, moveNumber } from './classification'

interface Props {
  review: Review
  whiteName: string
  blackName: string
  onSelect: (position: number) => void
}

export function ReviewSummary({ review, whiteName, blackName, onSelect }: Props) {
  const accuracy = (a: number | null) => (a === null ? '–' : a.toFixed(1))
  const byPly = new Map(review.moves.map((m) => [m.ply, m]))
  return (
    <div className="flex flex-col gap-4">
      {review.opening && (
        <p className="text-sm text-gray-600">
          Apertura: <strong>{review.opening.name}</strong> ({review.opening.eco})
        </p>
      )}
      <table className="w-full text-sm" aria-label="Resumen">
        <thead>
          <tr className="text-gray-500">
            <th />
            <th className="text-right font-normal">{whiteName}</th>
            <th className="text-right font-normal">{blackName}</th>
          </tr>
        </thead>
        <tbody>
          <tr className="text-base font-semibold">
            <td>Precisión</td>
            <td className="text-right">{accuracy(review.white.accuracy)}</td>
            <td className="text-right">{accuracy(review.black.accuracy)}</td>
          </tr>
          {CLASS_ORDER.map((c) => (
            <tr key={c}>
              <td className="flex items-center gap-1">
                <span
                  className="inline-block w-6 text-center text-xs font-bold"
                  style={{ color: CLASSIFICATIONS[c].color }}
                >
                  {CLASSIFICATIONS[c].mark}
                </span>
                {CLASSIFICATIONS[c].label}
              </td>
              <td className="text-right">{review.white.counts[c]}</td>
              <td className="text-right">{review.black.counts[c]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <h3 className="mb-1 text-sm font-semibold">Momentos clave</h3>
        {review.key_moments.length === 0 ? (
          <p className="text-sm text-gray-500">Ninguno: ¡partida limpia!</p>
        ) : (
          <ul aria-label="Momentos clave" className="flex flex-wrap gap-2">
            {review.key_moments.map((ply) => {
              const move = byPly.get(ply)
              if (!move) return null
              const meta = CLASSIFICATIONS[move.classification]
              return (
                <li key={ply}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(ply + 1)
                    }}
                    className="rounded-full border px-2 py-0.5 text-sm hover:bg-gray-100"
                    style={{ borderColor: meta.color }}
                  >
                    {moveNumber(ply)} {move.san}
                    <span className="ml-1 font-bold" style={{ color: meta.color }}>
                      {move.symbol}
                    </span>
                    {move.delta >= 0.5 && (
                      <span className="ml-1 text-gray-500">−{move.delta.toFixed(0)} %</span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
