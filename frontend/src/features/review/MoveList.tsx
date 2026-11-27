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
    // Keep the selected move visible by scrolling the list only (never the page): on every
    // move change and whenever the list is resized (the coach card above grows or shrinks).
    const box = container.current
    if (!box) return
    const reveal = () => {
      const item = selected.current
      if (!item || box.scrollHeight <= box.clientHeight) return
      const b = box.getBoundingClientRect()
      const r = item.getBoundingClientRect()
      if (r.top < b.top) box.scrollTop -= b.top - r.top + 8
      else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom + 8
    }
    reveal()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(reveal)
    observer.observe(box)
    return () => {
      observer.disconnect()
    }
  }, [position, moves.length])

  const cells: (ListMove | null)[] = blackStarts ? [null, ...moves] : [...moves]
  const rows: (ListMove | null)[][] = []
  for (let i = 0; i < cells.length; i += 2) rows.push(cells.slice(i, i + 2))

  return (
    <div
      ref={container}
      data-testid="move-list"
      className="relative min-h-0 flex-1 overflow-y-auto"
    >
      <ol aria-label="Jugadas" className="text-sm">
        {rows.map((row, r) => (
          <li
            key={r}
            className="tabular grid grid-cols-[2.75rem_1fr_1fr] items-center gap-1 rounded odd:bg-overlay"
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
                    isSelected ? 'bg-selected text-fg' : 'text-fg/90 hover:bg-overlay'
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
