import type { MoveRecord } from '../../api/games'
import { moveRows } from './gameText'

export function MoveList({ moves, initialFen }: { moves: MoveRecord[]; initialFen: string }) {
  if (moves.length === 0) {
    return <p className="text-sm text-muted">Aún no hay jugadas.</p>
  }
  return (
    <ol aria-label="Jugadas" className="max-h-80 overflow-y-auto font-mono text-sm">
      {moveRows(
        moves.map((m) => m.san),
        initialFen,
      ).map(([number, white, black]) => (
        <li key={number} className="grid grid-cols-[2.5rem_1fr_1fr] gap-1 odd:bg-white/[0.03]">
          <span className="text-muted">{number}.</span>
          <span>{white}</span>
          <span>{black}</span>
        </li>
      ))}
    </ol>
  )
}
