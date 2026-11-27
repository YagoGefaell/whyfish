import { createElement, type CSSProperties } from 'react'
import type { PieceRenderObject } from 'react-chessboard'
import { PieceImage } from './pieces'
import { PIECE_CODES } from './pieceUrls'

/**
 * Style for the content of a square (our squareRenderer). react-chessboard puts each piece in an
 * unsized div inside a flex-centred square, so a 100% piece resolved against its own content and
 * sat at the top of the square. Pinned to the square's edges, as a grid with stretched items, the
 * content (and the piece in it) takes exactly the whole square.
 */
export const SQUARE_CONTENT: CSSProperties = {
  position: 'absolute',
  inset: 0,
  display: 'grid',
  placeItems: 'stretch',
}

/** Highlights shared by every board (colours: the board tokens of the chosen board). */
export const LAST_MOVE_STYLE: CSSProperties = { backgroundColor: 'var(--color-board-last-move)' }
export const CHECK_STYLE: CSSProperties = {
  backgroundImage: 'radial-gradient(circle, var(--color-board-check) 0%, transparent 75%)',
}

/** Piece renderers for react-chessboard: the same component at rest and while dragged. */
const BOARD_PIECES: PieceRenderObject = Object.fromEntries(
  PIECE_CODES.map((code) => [code, () => createElement(PieceImage, { code })]),
)

/** Board look shared by every board (colours: board tokens in theme/tokens.css, per board). */
export const BOARD_COLORS: {
  pieces: PieceRenderObject
  draggingPieceStyle: CSSProperties
  draggingPieceGhostStyle: CSSProperties
  darkSquareStyle: CSSProperties
  lightSquareStyle: CSSProperties
  darkSquareNotationStyle: CSSProperties
  lightSquareNotationStyle: CSSProperties
  alphaNotationStyle: CSSProperties
  numericNotationStyle: CSSProperties
  boardStyle: CSSProperties
} = {
  pieces: BOARD_PIECES,
  // The library scales the dragged piece by 1.2; keep it the size it has at rest.
  draggingPieceStyle: { transform: 'none' },
  // The piece left behind on the origin square while dragging, as faint as on Lichess.
  draggingPieceGhostStyle: { opacity: 0.3 },
  darkSquareStyle: {
    backgroundColor: 'var(--color-board-dark)',
    backgroundImage: 'var(--board-dark-image)',
  },
  lightSquareStyle: {
    backgroundColor: 'var(--color-board-light)',
    backgroundImage: 'var(--board-light-image)',
  },
  darkSquareNotationStyle: { color: 'var(--color-board-coord-dark)', fontWeight: 600 },
  lightSquareNotationStyle: { color: 'var(--color-board-coord-light)', fontWeight: 600 },
  // Coordinates above the pieces (the square content is positioned, so it would cover them).
  alphaNotationStyle: { zIndex: 1, pointerEvents: 'none' },
  numericNotationStyle: { zIndex: 1, pointerEvents: 'none' },
  boardStyle: {
    borderRadius: 'var(--board-radius)',
    overflow: 'hidden',
  },
}
