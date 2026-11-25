import { createElement, type CSSProperties } from 'react'
import type { PieceRenderObject } from 'react-chessboard'
import { PieceImage } from './pieces'
import { PIECE_URLS } from './pieceUrls'

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

/** Piece renderers for react-chessboard: the same component at rest and while dragged. */
const BOARD_PIECES: PieceRenderObject = Object.fromEntries(
  Object.keys(PIECE_URLS).map((code) => [code, () => createElement(PieceImage, { code })]),
)

/** Board look shared by the play and review boards (sober green / cream, cburnett pieces). */
export const BOARD_COLORS: {
  pieces: PieceRenderObject
  draggingPieceStyle: CSSProperties
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
  darkSquareStyle: { backgroundColor: '#739552' },
  lightSquareStyle: { backgroundColor: '#ebecd0' },
  darkSquareNotationStyle: { color: '#ebecd0', fontWeight: 600 },
  lightSquareNotationStyle: { color: '#739552', fontWeight: 600 },
  // Coordinates above the pieces (the square content is positioned, so it would cover them).
  alphaNotationStyle: { zIndex: 1, pointerEvents: 'none' },
  numericNotationStyle: { zIndex: 1, pointerEvents: 'none' },
  boardStyle: { borderRadius: '6px', overflow: 'hidden' },
}
