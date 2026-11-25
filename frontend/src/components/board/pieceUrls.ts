import bB from '../../assets/pieces/cburnett/bB.svg'
import bK from '../../assets/pieces/cburnett/bK.svg'
import bN from '../../assets/pieces/cburnett/bN.svg'
import bP from '../../assets/pieces/cburnett/bP.svg'
import bQ from '../../assets/pieces/cburnett/bQ.svg'
import bR from '../../assets/pieces/cburnett/bR.svg'
import wB from '../../assets/pieces/cburnett/wB.svg'
import wK from '../../assets/pieces/cburnett/wK.svg'
import wN from '../../assets/pieces/cburnett/wN.svg'
import wP from '../../assets/pieces/cburnett/wP.svg'
import wQ from '../../assets/pieces/cburnett/wQ.svg'
import wR from '../../assets/pieces/cburnett/wR.svg'

/** cburnett piece set (BSD, see assets/pieces/cburnett/LICENSE.md). Keys: "wK", "bP"... */
export const PIECE_URLS: Record<string, string> = { wK, wQ, wR, wB, wN, wP, bK, bQ, bR, bB, bN, bP }

/** Share of the square taken by a piece on the board. */
export const PIECE_SCALE = '85%'
