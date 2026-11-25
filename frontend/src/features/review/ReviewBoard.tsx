import { useMemo, useState, type CSSProperties } from 'react'
import { Chessboard, type PieceDropHandlerArgs, type SquareHandlerArgs } from 'react-chessboard'
import { Chess } from 'chess.js'
import type { Color } from '../../api/games'
import { PromotionDialog } from '../../components/board/PromotionDialog'
import { resolveDrop, type PromotionPiece } from '../../components/board/moves'

export interface BoardArrow {
  from: string
  to: string
  color: string
}

export interface SquareBadge {
  square: string
  mark: string
  color: string
  label: string
}

interface Props {
  fen: string
  orientation: Color
  arrows: BoardArrow[]
  highlight: { from: string; to: string; color: string } | null
  badge: SquareBadge | null
  /** A legal move made on the board (any side to move): enters/extends exploration. */
  onMove: (uci: string) => void
}

export function ReviewBoard({ fen, orientation, arrows, highlight, badge, onMove }: Props) {
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null)
  const turn: Color = new Chess(fen).turn() === 'w' ? 'white' : 'black'

  const squareStyles = useMemo(() => {
    const styles: Record<string, CSSProperties> = {}
    if (highlight) {
      const bg = { backgroundColor: `${highlight.color}66` }
      styles[highlight.from] = bg
      styles[highlight.to] = bg
    }
    return styles
  }, [highlight])

  const squareRenderer = ({
    square,
    children,
  }: SquareHandlerArgs & { children?: React.ReactNode }) => (
    <div style={{ width: '100%', height: '100%', position: 'relative', ...squareStyles[square] }}>
      {children}
      {badge?.square === square && (
        <span
          data-testid="move-badge"
          aria-label={badge.label}
          title={badge.label}
          className="pointer-events-none absolute -right-1 -top-1 z-10 flex h-[38%] min-h-4 w-[38%] min-w-4 items-center justify-center rounded-full border-2 border-white text-[min(1.6vw,13px)] font-bold leading-none text-white shadow"
          style={{ backgroundColor: badge.color }}
        >
          {badge.mark}
        </span>
      )}
    </div>
  )

  const onPieceDrop = ({ sourceSquare, targetSquare }: PieceDropHandlerArgs): boolean => {
    const drop = resolveDrop(fen, sourceSquare, targetSquare)
    switch (drop.kind) {
      case 'illegal':
        return false
      case 'promotion':
        setPromotion({ from: drop.from, to: drop.to })
        return false
      case 'move':
        onMove(drop.uci)
        return true
    }
  }

  const choose = (piece: PromotionPiece) => {
    if (promotion) onMove(promotion.from + promotion.to + piece)
    setPromotion(null)
  }

  return (
    <div className="relative w-full">
      <Chessboard
        options={{
          id: 'review-board',
          position: fen,
          boardOrientation: orientation,
          arrows: arrows.map((a) => ({ startSquare: a.from, endSquare: a.to, color: a.color })),
          allowDrawingArrows: false,
          onPieceDrop,
          squareRenderer,
        }}
      />
      {promotion && (
        <PromotionDialog
          color={turn}
          onSelect={choose}
          onCancel={() => {
            setPromotion(null)
          }}
        />
      )}
    </div>
  )
}
