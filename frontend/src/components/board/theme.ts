import { createElement, type CSSProperties } from 'react'
import type { PieceRenderObject } from 'react-chessboard'
import { PIECE_SCALE, PIECE_URLS } from './pieceUrls'

/** Piece renderers for react-chessboard: the cburnett image centred at 85% of the square. */
const BOARD_PIECES: PieceRenderObject = Object.fromEntries(
  Object.entries(PIECE_URLS).map(([code, url]) => [
    code,
    () =>
      createElement(
        'div',
        {
          'data-piece-image': code,
          style: {
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          },
        },
        createElement('img', {
          src: url,
          alt: '',
          draggable: false,
          style: {
            width: PIECE_SCALE,
            height: PIECE_SCALE,
            display: 'block',
            pointerEvents: 'none',
          },
        }),
      ),
  ]),
)

/** Board look shared by the play and review boards (sober green / cream, cburnett pieces). */
export const BOARD_COLORS: {
  pieces: PieceRenderObject
  darkSquareStyle: CSSProperties
  lightSquareStyle: CSSProperties
  darkSquareNotationStyle: CSSProperties
  lightSquareNotationStyle: CSSProperties
  boardStyle: CSSProperties
} = {
  pieces: BOARD_PIECES,
  darkSquareStyle: { backgroundColor: '#739552' },
  lightSquareStyle: { backgroundColor: '#ebecd0' },
  darkSquareNotationStyle: { color: '#ebecd0', fontWeight: 600 },
  lightSquareNotationStyle: { color: '#739552', fontWeight: 600 },
  boardStyle: { borderRadius: '6px', overflow: 'hidden' },
}
