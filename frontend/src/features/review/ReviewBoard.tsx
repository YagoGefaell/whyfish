import { Chess } from 'chess.js'
import { useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Chessboard,
  defaultArrowOptions,
  type PieceDropHandlerArgs,
  type SquareHandlerArgs,
} from 'react-chessboard'
import type { Classification } from '../../api/analysis'
import type { Color } from '../../api/games'
import { ClassBadge } from '../../components/ClassBadge'
import { BOARD_COLORS, SQUARE_CONTENT } from '../../components/board/theme'
import { PromotionDialog } from '../../components/board/PromotionDialog'
import { resolveDrop, type PromotionPiece } from '../../components/board/moves'
import { CLASSIFICATIONS } from './classification'

export interface BoardArrow {
  from: string
  to: string
  color: string
}

/** The move shown on the board: neutral highlight on its origin, class colour on its target. */
export interface ShownMove {
  from: string
  to: string
  classification: Classification | null // null = no classification (exploring, not analysed)
}

interface Props {
  fen: string
  orientation: Color
  arrows: BoardArrow[]
  shownMove: ShownMove | null
  /** Slide pieces (single steps) or jump (long jumps). */
  animate: boolean
  /** A legal move made on the board (any side to move): enters/extends exploration. */
  onMove: (uci: string) => void
}

/** Best-move arrow: intense green, thicker and more opaque than the default, visible over pieces. */
const ARROW_OPTIONS = { ...defaultArrowOptions, opacity: 0.8, arrowWidthDenominator: 4 }

/** For moves without a classification (exploring, not analysed yet). */
const NEUTRAL_FROM = 'rgba(255, 255, 255, 0.22)'
const NEUTRAL_TO = 'rgba(255, 255, 255, 0.36)'
/** Hex alpha suffixes: origin ~30 %, target ~55 %. */
const FROM_ALPHA = '4d'
const TO_ALPHA = '8c'

export function ReviewBoard({ fen, orientation, arrows, shownMove, animate, onMove }: Props) {
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null)
  const turn: Color = new Chess(fen).turn() === 'w' ? 'white' : 'black'

  const squareStyles = useMemo(() => {
    const styles: Record<string, CSSProperties> = {}
    if (shownMove) {
      const color = shownMove.classification
        ? CLASSIFICATIONS[shownMove.classification].color
        : null
      styles[shownMove.from] = { backgroundColor: color ? color + FROM_ALPHA : NEUTRAL_FROM }
      styles[shownMove.to] = { backgroundColor: color ? color + TO_ALPHA : NEUTRAL_TO }
    }
    return styles
  }, [shownMove])

  const badgeSquare = shownMove?.classification ? shownMove.to : null
  const squareRenderer = ({ square, children }: SquareHandlerArgs & { children?: ReactNode }) => (
    <div
      style={{
        ...SQUARE_CONTENT,
        ...squareStyles[square],
      }}
    >
      {children}
      {badgeSquare === square && shownMove?.classification && (
        <span
          data-testid="move-badge"
          className="pointer-events-none absolute -top-[14%] -right-[14%] z-10 h-[46%] w-[46%] drop-shadow-md"
        >
          <ClassBadge
            classification={shownMove.classification}
            size={100}
            className="h-full w-full"
          />
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
    <div data-testid="review-board" className="relative w-full overflow-visible">
      <Chessboard
        options={{
          id: 'review-board',
          position: fen,
          boardOrientation: orientation,
          arrows: arrows.map((a) => ({ startSquare: a.from, endSquare: a.to, color: a.color })),
          allowDrawingArrows: false,
          arrowOptions: ARROW_OPTIONS,
          showAnimations: animate,
          animationDurationInMs: 200,
          onPieceDrop,
          squareRenderer,
          ...BOARD_COLORS,
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
