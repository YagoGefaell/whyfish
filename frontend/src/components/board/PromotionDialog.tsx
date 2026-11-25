import type { Color } from '../../api/games'
import type { PromotionPiece } from './moves'

const PIECES: { piece: PromotionPiece; label: string; white: string; black: string }[] = [
  { piece: 'q', label: 'Dama', white: '♕', black: '♛' },
  { piece: 'r', label: 'Torre', white: '♖', black: '♜' },
  { piece: 'b', label: 'Alfil', white: '♗', black: '♝' },
  { piece: 'n', label: 'Caballo', white: '♘', black: '♞' },
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
      className="absolute inset-0 z-10 flex items-center justify-center bg-black/40"
    >
      <div className="rounded-lg bg-white p-4 shadow-xl">
        <p className="mb-3 text-center font-medium">Promocionar a…</p>
        <div className="flex gap-2">
          {PIECES.map(({ piece, label, white, black }) => (
            <button
              key={piece}
              type="button"
              aria-label={label}
              title={label}
              onClick={() => {
                onSelect(piece)
              }}
              className="h-16 w-16 rounded border border-gray-300 text-5xl leading-none hover:bg-amber-100"
            >
              {color === 'white' ? white : black}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="mt-3 w-full text-sm text-gray-600 hover:underline"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
