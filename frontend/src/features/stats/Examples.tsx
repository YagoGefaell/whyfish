import { Link } from 'react-router'
import type { StatExample } from '../../api/stats'

const SYMBOL: Record<string, string> = { blunder: '??', mistake: '?', miss: '✗', inaccuracy: '?!' }

/** "21…dxc3" from a 0-based ply. */
function moveLabel(ply: number, san: string): string {
  const number = Math.floor(ply / 2) + 1
  return ply % 2 === 0 ? `${String(number)}.${san}` : `${String(number)}…${san}`
}

/** The positions behind a figure, each opening the review at that move. */
export function Examples({ examples, label }: { examples: StatExample[]; label: string }) {
  if (examples.length === 0) return <p className="text-sm text-muted">Sin posiciones.</p>
  return (
    <ul aria-label={label} className="flex flex-col gap-1 text-sm">
      {examples.map((e) => (
        <li key={`${String(e.game_id)}-${String(e.ply)}`}>
          <Link
            to={`/review/${String(e.game_id)}?ply=${String(e.ply)}`}
            className="flex flex-wrap items-baseline gap-x-2 rounded-md px-2 py-1 hover:bg-panel-2"
          >
            <span className="tabular font-semibold">
              {moveLabel(e.ply, e.san)}
              {SYMBOL[e.classification] ?? ''}
            </span>
            <span className="text-muted">
              vs {e.opponent ?? '?'} · {new Date(e.date).toLocaleDateString('es-ES')}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
