import { useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Chessboard,
  type PieceDropHandlerArgs,
  type PieceHandlerArgs,
  type SquareHandlerArgs,
} from 'react-chessboard'
import type { Color } from '../../api/games'
import { checkedKingSquare, resolveDrop, type PromotionPiece } from './moves'
import { PromotionDialog } from './PromotionDialog'
import { BOARD_COLORS, SQUARE_CONTENT } from './theme'

const LAST_MOVE_STYLE: CSSProperties = { backgroundColor: 'rgba(255, 213, 79, 0.55)' }
const HINT_STYLE: CSSProperties = { boxShadow: 'inset 0 0 0 4px rgba(37, 99, 235, 0.9)' }
const CHECK_STYLE: CSSProperties = {
  background: 'radial-gradient(circle, rgba(220, 38, 38, 0.85) 0%, rgba(220, 38, 38, 0) 75%)',
}

interface Props {
  fen: string
  orientation: Color
  playerColor: Color
  /** Whether the player may move pieces now. */
  interactive: boolean
  lastMove?: { from: string; to: string } | null
  hintSquare?: string | null
  onMove: (uci: string) => void
}

export function Board({
  fen,
  orientation,
  playerColor,
  interactive,
  lastMove,
  hintSquare,
  onMove,
}: Props) {
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(
    null,
  )

  const squareStyles = useMemo(() => {
    const styles: Record<string, CSSProperties> = {}
    if (lastMove) {
      styles[lastMove.from] = LAST_MOVE_STYLE
      styles[lastMove.to] = LAST_MOVE_STYLE
    }
    const checked = checkedKingSquare(fen)
    if (checked) styles[checked] = { ...styles[checked], ...CHECK_STYLE }
    if (hintSquare) styles[hintSquare] = { ...styles[hintSquare], ...HINT_STYLE }
    return styles
  }, [fen, lastMove, hintSquare])

  const squareRenderer = ({ square, children }: SquareHandlerArgs & { children?: ReactNode }) => (
    <div style={{ ...SQUARE_CONTENT, ...squareStyles[square] }}>{children}</div>
  )

  const playerPrefix = playerColor === 'white' ? 'w' : 'b'

  const canDragPiece = ({ piece }: PieceHandlerArgs) =>
    interactive && piece.pieceType.startsWith(playerPrefix)

  const onPieceDrop = ({ sourceSquare, targetSquare }: PieceDropHandlerArgs): boolean => {
    if (!interactive) return false
    const drop = resolveDrop(fen, sourceSquare, targetSquare)
    switch (drop.kind) {
      case 'illegal':
        return false
      case 'promotion':
        setPendingPromotion({ from: drop.from, to: drop.to })
        return false
      case 'move':
        onMove(drop.uci)
        return true
    }
  }

  const choosePromotion = (piece: PromotionPiece) => {
    if (pendingPromotion) onMove(pendingPromotion.from + pendingPromotion.to + piece)
    setPendingPromotion(null)
  }

  return (
    <div className="relative w-full">
      <Chessboard
        options={{
          id: 'play-board',
          position: fen,
          boardOrientation: orientation,
          allowDragging: interactive,
          canDragPiece,
          onPieceDrop,
          squareRenderer,
          allowDrawingArrows: true,
          ...BOARD_COLORS,
        }}
      />
      {pendingPromotion && (
        <PromotionDialog
          color={playerColor}
          onSelect={choosePromotion}
          onCancel={() => {
            setPendingPromotion(null)
          }}
        />
      )}
    </div>
  )
}
