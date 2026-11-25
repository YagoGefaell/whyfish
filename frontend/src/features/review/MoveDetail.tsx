import type { MoveReview, WhiteEval } from '../../api/analysis'
import { CLASSIFICATIONS, evalLabel, moveNumber } from './classification'
import { MoveExplanation } from './MoveExplanation'

interface Props {
  move: MoveReview | null
  evalAfter: WhiteEval | null
  /** Show `line` from the position before the move (best line) or after it (played line). */
  onLine: (from: 'before' | 'after', sans: string[], index: number) => void
}

function Line({
  sans,
  onPick,
  label,
}: {
  sans: string[]
  onPick: (index: number) => void
  label: string
}) {
  return (
    <span className="inline-flex flex-wrap gap-1" aria-label={label}>
      {sans.map((san, i) => (
        <button
          key={i}
          type="button"
          onClick={() => {
            onPick(i)
          }}
          className="rounded bg-gray-100 px-1 font-mono text-sm hover:bg-blue-100"
        >
          {san}
        </button>
      ))}
    </span>
  )
}

export function MoveDetail({ move, evalAfter, onLine }: Props) {
  if (!move) {
    return <p className="text-sm text-gray-500">Posición inicial. Usa → para avanzar.</p>
  }
  const meta = CLASSIFICATIONS[move.classification]
  const isBest = move.best_uci === move.uci
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span
          className="flex h-7 min-w-7 items-center justify-center rounded-full px-1 text-sm font-bold text-white"
          style={{ backgroundColor: meta.color }}
          aria-hidden="true"
        >
          {meta.mark}
        </span>
        <h3 className="text-lg font-semibold">
          {moveNumber(move.ply)} {move.san} ·{' '}
          <span style={{ color: meta.color }}>{meta.label}</span>
        </h3>
      </div>
      <p className="text-sm text-gray-600">
        Probabilidad de ganar de {move.color === 'white' ? 'blancas' : 'negras'}:{' '}
        {move.win_before.toFixed(0)} % → {move.win_after.toFixed(0)} %
        {move.delta >= 0.5 && ` (−${move.delta.toFixed(1)})`}
        {evalAfter && ` · evaluación (blancas) ${evalLabel(evalAfter)}`}
      </p>
      {!isBest && move.best_san && (
        <p className="text-sm">
          Mejor era <strong className="font-mono">{move.best_san}</strong>:{' '}
          <Line
            label="Línea de la mejor jugada"
            sans={move.best_line}
            onPick={(i) => {
              onLine('before', move.best_line, i)
            }}
          />
        </p>
      )}
      {move.played_line.length > 0 && (
        <p className="text-sm">
          Tras {move.san}, la continuación del motor:{' '}
          <Line
            label="Continuación tras la jugada"
            sans={move.played_line}
            onPick={(i) => {
              onLine('after', move.played_line, i)
            }}
          />
        </p>
      )}
      <MoveExplanation move={move} />
    </div>
  )
}
