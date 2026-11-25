import { useEffect, useRef } from 'react'
import type { Classification } from '../../api/analysis'
import { ClassBadge } from '../../components/ClassBadge'
import { CLASSIFICATIONS } from './classification'

export interface ListMove {
  ply: number
  san: string
  classification: Classification | null
}

interface Props {
  moves: ListMove[]
  /** Selected position (0 = start): the selected move is moves[position - 1]. */
  position: number
  onSelect: (position: number) => void
  firstMoveNumber: number
  blackStarts: boolean
}

/** Two columns (white | black) with the move number; badges only on !!, !, ?!, ?, ?? and ✗. */
export function MoveList({ moves, position, onSelect, firstMoveNumber, blackStarts }: Props) {
  const selected = useRef<HTMLButtonElement | null>(null)
  const container = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    // Keep the selected move visible by scrolling the list only (never the page).
    const box = container.current
    const item = selected.current
    if (!box || !item || box.scrollHeight <= box.clientHeight) return
    const top = item.offsetTop - box.offsetTop
    if (top < box.scrollTop) box.scrollTop = top - 8
    else if (top + item.offsetHeight > box.scrollTop + box.clientHeight) {
      box.scrollTop = top + item.offsetHeight - box.clientHeight + 8
    }
  }, [position])

  const cells: (ListMove | null)[] = blackStarts ? [null, ...moves] : [...moves]
  const rows: (ListMove | null)[][] = []
  for (let i = 0; i < cells.length; i += 2) rows.push(cells.slice(i, i + 2))

  return (
    <div ref={container} className="relative min-h-0 flex-1 overflow-y-auto">
      <ol aria-label="Jugadas" className="text-sm">
        {rows.map((row, r) => (
          <li
            key={r}
            className="tabular grid grid-cols-[2.75rem_1fr_1fr] items-center gap-1 rounded odd:bg-white/[0.03]"
          >
            <span className="py-1 pl-2 text-muted">{firstMoveNumber + r}.</span>
            {[0, 1].map((c) => {
              const move = row[c]
              if (!move) return <span key={c} />
              const isSelected = move.ply + 1 === position
              const showBadge =
                move.classification !== null && CLASSIFICATIONS[move.classification].inList
              return (
                <button
                  key={c}
                  type="button"
                  ref={isSelected ? selected : undefined}
                  aria-current={isSelected ? 'true' : undefined}
                  onClick={() => {
                    onSelect(move.ply + 1)
                  }}
                  className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-left font-medium ${
                    isSelected ? 'bg-[#4b4844] text-fg' : 'text-fg/90 hover:bg-white/5'
                  }`}
                >
                  {showBadge && move.classification && (
                    <ClassBadge classification={move.classification} size={16} />
                  )}
                  <span>{move.san}</span>
                </button>
              )
            })}
          </li>
        ))}
      </ol>
    </div>
  )
}
