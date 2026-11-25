import { PIECE_URLS } from './pieceUrls'

/** A cburnett piece image ("wK", "bP"...). */
export function PieceImage({ code, className = '' }: { code: string; className?: string }) {
  return (
    <img
      src={PIECE_URLS[code]}
      alt=""
      draggable={false}
      className={`pointer-events-none select-none ${className}`}
    />
  )
}
