import { useNavigate } from 'react-router'
import type { AccuracyPoint } from '../../api/stats'

const W = 600
const H = 160
const PAD = 24

/** Accuracy per game (dots, click -> review) and its moving average (line). Own SVG. */
export function AccuracyChart({ points }: { points: AccuracyPoint[] }) {
  const navigate = useNavigate()
  if (points.length === 0) return null
  const x = (i: number) =>
    points.length === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (points.length - 1)
  const y = (v: number) => H - PAD - ((v - 0) * (H - 2 * PAD)) / 100
  const line = points.map(
    (p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.average).toFixed(1)}`,
  )
  return (
    <svg
      viewBox={`0 0 ${String(W)} ${String(H)}`}
      role="img"
      aria-label="Evolución de la precisión"
      className="h-auto w-full"
    >
      {[25, 50, 75].map((v) => (
        <g key={v}>
          <line x1={PAD} x2={W - PAD} y1={y(v)} y2={y(v)} stroke="currentColor" opacity={0.12} />
          <text x={2} y={y(v) + 4} fontSize={10} fill="currentColor" opacity={0.5}>
            {v}
          </text>
        </g>
      ))}
      <path
        d={line.join(' ')}
        fill="none"
        style={{ stroke: 'var(--color-chart-line)' }}
        strokeWidth={2.5}
      />
      {points.map((p, i) => (
        <circle
          key={p.game_id}
          cx={x(i)}
          cy={y(p.accuracy)}
          r={4}
          style={{ fill: 'var(--color-chart-dot)' }}
          opacity={0.7}
          className="cursor-pointer"
          onClick={() => {
            void navigate(`/review/${String(p.game_id)}`)
          }}
        >
          <title>
            {new Date(p.date).toLocaleDateString('es-ES')}: {p.accuracy.toFixed(1)} %
          </title>
        </circle>
      ))}
    </svg>
  )
}
