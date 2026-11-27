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
import { BOARD_COLORS, CHECK_STYLE, SQUARE_CONTENT } from '../../components/board/theme'
import { PromotionDialog } from '../../components/board/PromotionDialog'
import { checkedKingSquare, resolveDrop, type PromotionPiece } from '../../components/board/moves'
import { resolveColor, usePrefs } from '../../theme/prefs'
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

/**
 * A square the explanation points at: piece in danger (red), target / saved piece (amber), or
 * the consequence of a good idea (green, "Ver la idea").
 */
export interface MarkedSquare {
  square: string
  role: 'danger' | 'target' | 'good'
}

interface Props {
  fen: string
  orientation: Color
  arrows: BoardArrow[]
  marks?: MarkedSquare[]
  shownMove: ShownMove | null
  /** Slide pieces (single steps) or jump (long jumps). */
  animate: boolean
  /** A legal move made on the board (any side to move): enters/extends exploration. */
  onMove: (uci: string) => void
  /** Pieces can be dragged (false while a sequence is being replayed). */
  interactive?: boolean
  /** Duration of the slide when `animate` (ms). */
  animationMs?: number
  /** Board id (squares are `#<id>-square-e4`); "review-board" by default. */
  id?: string
}

/** Arrows: thicker and more opaque than the default, visible over pieces (contrast.test.ts). */
const ARROW_OPTIONS = { ...defaultArrowOptions, opacity: 0.8, arrowWidthDenominator: 4 }

/** For moves without a classification (exploring, not analysed yet). */
const NEUTRAL_FROM = 'color-mix(in srgb, var(--color-board-neutral) 61%, transparent)'
const NEUTRAL_TO = 'var(--color-board-neutral)'
/** The classification colour over the square: origin 30 %, target 55 %. */
const tint = (color: string, percent: number) =>
  `color-mix(in srgb, ${color} ${String(percent)}%, transparent)`
/** Explanation marks: a ring plus a tint over whatever colour the square already has. */
function mark(color: string, percent: number): CSSProperties {
  const fill = tint(color, percent)
  return {
    boxShadow: `inset 0 0 0 4px ${tint(color, 95)}`,
    backgroundImage: `linear-gradient(${fill}, ${fill})`,
  }
}
const MARK_STYLES: Record<MarkedSquare['role'], CSSProperties> = {
  danger: mark('var(--color-board-danger)', 35),
  target: mark('var(--color-board-target)', 30),
  good: mark('var(--color-board-good)', 35),
}

export function ReviewBoard({
  fen,
  orientation,
  arrows,
  marks = [],
  shownMove,
  animate,
  onMove,
  interactive = true,
  animationMs = 200,
  id = 'review-board',
}: Props) {
  // Re-render when the board or piece set changes: arrows need literal colours.
  usePrefs()
  const [promotion, setPromotion] = useState<{ from: string; to: string } | null>(null)
  const turn: Color = new Chess(fen).turn() === 'w' ? 'white' : 'black'

  const squareStyles = useMemo(() => {
    const styles: Record<string, CSSProperties> = {}
    if (shownMove) {
      const color = shownMove.classification
        ? CLASSIFICATIONS[shownMove.classification].color
        : null
      styles[shownMove.from] = { backgroundColor: color ? tint(color, 30) : NEUTRAL_FROM }
      styles[shownMove.to] = { backgroundColor: color ? tint(color, 55) : NEUTRAL_TO }
    }
    const checked = checkedKingSquare(fen)
    if (checked) styles[checked] = { ...styles[checked], ...CHECK_STYLE }
    for (const mark of marks) {
      styles[mark.square] = { ...styles[mark.square], ...MARK_STYLES[mark.role] }
    }
    return styles
  }, [fen, shownMove, marks])

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
    <div data-testid={id} className="relative w-full overflow-visible">
      <Chessboard
        options={{
          id,
          position: fen,
          boardOrientation: orientation,
          // SVG attributes: a token has to be a literal colour here.
          arrows: arrows.map((a) => ({
            startSquare: a.from,
            endSquare: a.to,
            color: resolveColor(a.color),
          })),
          allowDrawingArrows: false,
          arrowOptions: ARROW_OPTIONS,
          showAnimations: animate,
          animationDurationInMs: animationMs,
          allowDragging: interactive,
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
