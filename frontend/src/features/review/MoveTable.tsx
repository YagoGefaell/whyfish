import { useEffect, useRef } from 'react'
import type { MoveReview } from '../../api/analysis'
import { CLASSIFICATIONS } from './classification'

interface Props {
  moves: MoveReview[]
  /** Selected position (0 = start): the selected move is moves[position - 1]. */
  position: number
  onSelect: (position: number) => void
  /** Number of the first move (games imported from a FEN may not start at 1). */
  firstMoveNumber: number
  blackStarts: boolean
}

export function MoveTable({ moves, position, onSelect, firstMoveNumber, blackStarts }: Props) {
  const selected = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    // scrollIntoView is missing in jsdom.
    if (typeof selected.current?.scrollIntoView === 'function') {
      selected.current.scrollIntoView({ block: 'nearest' })
    }
  }, [position])

  const cells: (MoveReview | null)[] = blackStarts ? [null, ...moves] : [...moves]
  const rows: (MoveReview | null)[][] = []
  for (let i = 0; i < cells.length; i += 2) rows.push(cells.slice(i, i + 2))

  return (
    <ol aria-label="Jugadas" className="max-h-80 overflow-y-auto font-mono text-sm">
      {rows.map((row, r) => (
        <li key={r} className="grid grid-cols-[2.5rem_1fr_1fr] gap-1 odd:bg-gray-50">
          <span className="py-0.5 text-gray-400">{firstMoveNumber + r}.</span>
          {[0, 1].map((c) => {
            const move = row[c]
            if (!move) return <span key={c} />
            const meta = CLASSIFICATIONS[move.classification]
            const isSelected = move.ply + 1 === position
            return (
              <button
                key={c}
                type="button"
                ref={isSelected ? selected : undefined}
                aria-current={isSelected ? 'true' : undefined}
                onClick={() => {
                  onSelect(move.ply + 1)
                }}
                className={`flex items-center gap-1 rounded px-1 py-0.5 text-left ${
                  isSelected ? 'bg-blue-100 font-semibold' : 'hover:bg-gray-100'
                }`}
              >
                <span>{move.san}</span>
                {move.symbol && (
                  <span
                    className="text-xs font-bold"
                    style={{ color: meta.color }}
                    title={meta.label}
                  >
                    {move.symbol}
                  </span>
                )}
              </button>
            )
          })}
        </li>
      ))}
    </ol>
  )
}
