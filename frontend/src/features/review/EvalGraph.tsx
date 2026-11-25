import type { MoveReview, WhiteEval } from '../../api/analysis'
import { CLASSIFICATIONS, moveNumber } from './classification'

interface Props {
  evals: WhiteEval[]
  moves: MoveReview[]
  keyMoments: number[]
  position: number
  onSelect: (position: number) => void
}

const MARKED = new Set(['brilliant', 'great', 'mistake', 'blunder', 'miss'])

/**
 * White's win% over the game. Each position has its own clickable column (no coordinate
 * maths, so it works the same in tests and browsers).
 */
export function EvalGraph({ evals, moves, keyMoments, position, onSelect }: Props) {
  const last = Math.max(1, evals.length - 1)
  const points = evals.map((e, i) => `${String(i)},${String(100 - e.win)}`).join(' ')
  const keySet = new Set(keyMoments)
  return (
    <div className="relative h-24 w-full select-none overflow-hidden rounded bg-gray-700">
      <svg
        viewBox={`0 0 ${String(last)} 100`}
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <polygon points={`0,100 ${points} ${String(last)},100`} className="fill-gray-100" />
        <line
          x1={0}
          x2={last}
          y1={50}
          y2={50}
          className="stroke-gray-400"
          strokeWidth={0.5}
          vectorEffect="non-scaling-stroke"
        />
        <line
          x1={position}
          x2={position}
          y1={0}
          y2={100}
          className="stroke-blue-500"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {moves.map((m) => {
        const marked = MARKED.has(m.classification) || keySet.has(m.ply)
        if (!marked) return null
        const pos = m.ply + 1
        return (
          <span
            key={m.ply}
            className={`pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white ${keySet.has(m.ply) ? 'ring-2 ring-blue-400' : ''}`}
            style={{
              left: `${String((pos / last) * 100)}%`,
              top: `${String(100 - (evals[pos]?.win ?? 50))}%`,
              backgroundColor: CLASSIFICATIONS[m.classification].color,
            }}
          />
        )
      })}
      <div className="absolute inset-0 flex">
        {evals.map((_, i) => (
          <button
            key={i}
            type="button"
            data-position={i}
            aria-label={
              i === 0 ? 'Posición inicial' : `Ir a ${moveNumber(i - 1)} ${moves[i - 1]?.san ?? ''}`
            }
            onClick={() => {
              onSelect(i)
            }}
            className="h-full flex-1 cursor-pointer hover:bg-blue-400/20 focus:outline-none"
          />
        ))}
      </div>
    </div>
  )
}
