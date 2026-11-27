import type { Color } from '../../api/games'
import type { PromotionPiece } from './moves'
import { PieceImage } from './pieces'

const PIECES: { piece: PromotionPiece; label: string; code: string }[] = [
  { piece: 'q', label: 'Dama', code: 'Q' },
  { piece: 'r', label: 'Torre', code: 'R' },
  { piece: 'b', label: 'Alfil', code: 'B' },
  { piece: 'n', label: 'Caballo', code: 'N' },
]

interface Props {
  color: Color
  onSelect: (piece: PromotionPiece) => void
  onCancel: () => void
}

export function PromotionDialog({ color, onSelect, onCancel }: Props) {
  return (
    <div
      role="dialog"
      aria-label="Elige la pieza de promoción"
      className="absolute inset-0 z-10 flex items-center justify-center bg-black/60"
    >
      <div className="rounded-lg bg-panel p-4 shadow-xl border border-line">
        <p className="mb-3 text-center font-medium">Promocionar a…</p>
        <div className="flex gap-2">
          {PIECES.map(({ piece, label, code }) => (
            <button
              key={piece}
              type="button"
              aria-label={label}
              title={label}
              onClick={() => {
                onSelect(piece)
              }}
              className="h-16 w-16 rounded-lg border border-line bg-panel-2 text-fg hover:bg-hover"
            >
              {/* Same piece as on the board: it fills the button like a square. */}
              <PieceImage code={(color === 'white' ? 'w' : 'b') + code} />
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="mt-3 w-full text-sm text-muted hover:underline"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
