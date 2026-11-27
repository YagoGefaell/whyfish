import type { MoveReview, WhiteEval } from '../../api/analysis'
import { CLASSIFICATIONS, GRAPH_MARKED, moveNumber } from './classification'

interface Props {
  evals: WhiteEval[]
  moves: MoveReview[]
  position: number
  onSelect: (position: number) => void
  className?: string
}

/**
 * White's win% over the game: white area grows from the bottom (white better = more white),
 * dark above. Dots on !!, ?, ?? and missed opportunities; vertical line on the current move.
 * Each position has its own clickable column (no coordinate maths).
 */
export function EvalGraph({ evals, moves, position, onSelect, className = '' }: Props) {
  const last = Math.max(1, evals.length - 1)
  const points = evals.map((e, i) => `${String(i)},${String(100 - e.win)}`).join(' ')
  return (
    <div
      data-testid="eval-graph"
      className={`relative w-full select-none overflow-hidden rounded-lg bg-eval-track ${className}`}
    >
      <svg
        viewBox={`0 0 ${String(last)} 100`}
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <polygon
          points={`0,100 ${points} ${String(last)},100`}
          style={{ fill: 'var(--color-eval-fill)' }}
        />
        <line
          x1={0}
          x2={last}
          y1={50}
          y2={50}
          style={{ stroke: 'var(--color-eval-mid)' }}
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
          strokeDasharray="3 3"
        />
        <line
          x1={position}
          x2={position}
          y1={0}
          y2={100}
          style={{ stroke: 'var(--color-chart-line)' }}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {moves.map((m) => {
        if (!GRAPH_MARKED.has(m.classification)) return null
        const pos = m.ply + 1
        return (
          <span
            key={m.ply}
            data-testid="graph-dot"
            className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-panel"
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
            className="h-full min-w-[3px] flex-1 cursor-pointer hover:bg-black/10 focus-visible:bg-black/15 focus-visible:outline-none"
          />
        ))}
      </div>
    </div>
  )
}
