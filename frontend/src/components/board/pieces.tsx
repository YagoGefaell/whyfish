import { usePrefs } from '../../theme/prefs'
import { pieceUrl } from './pieceUrls'

/**
 * A piece of the set chosen in Ajustes ("wK", "bP"...) filling its box: 100% wide and high, no extra scaling. The SVG
 * (viewBox 0 0 45 45, default preserveAspectRatio xMidYMid meet) carries its own inner margin, as
 * on Lichess, so in a square box it is centred exactly. Used on the board, for the dragged piece
 * and in the promotion dialog.
 */
export function PieceImage({ code }: { code: string }) {
  const { pieces } = usePrefs()
  return (
    <img
      src={pieceUrl(code, pieces)}
      alt=""
      draggable={false}
      data-piece-image={code}
      className="pointer-events-none block h-full w-full select-none"
    />
  )
}
