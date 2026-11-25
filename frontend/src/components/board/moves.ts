import { Chess, type Square } from 'chess.js'

export type PromotionPiece = 'q' | 'r' | 'b' | 'n'

export type DropResult =
  | { kind: 'illegal' }
  | { kind: 'move'; uci: string }
  | { kind: 'promotion'; from: string; to: string }

/** Classify a drag-and-drop attempt in `fen` (client-side preview; the server has the final say). */
export function resolveDrop(fen: string, from: string, to: string | null): DropResult {
  if (to === null || from === to) return { kind: 'illegal' }
  const chess = new Chess(fen)
  const candidates = chess
    .moves({ square: from as Square, verbose: true })
    .filter((m) => m.to === to)
  if (candidates.length === 0) return { kind: 'illegal' }
  if (candidates.some((m) => m.promotion !== undefined)) return { kind: 'promotion', from, to }
  return { kind: 'move', uci: from + to }
}

/** FEN after playing `uci` in `fen`, or null if the move is illegal. */
export function applyUci(fen: string, uci: string): string | null {
  const chess = new Chess(fen)
  try {
    chess.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci.slice(4) || undefined })
  } catch {
    return null
  }
  return chess.fen()
}

/** Square of the king of the side to move if it is in check. */
export function checkedKingSquare(fen: string): string | null {
  const chess = new Chess(fen)
  if (!chess.inCheck()) return null
  const turn = chess.turn()
  for (const row of chess.board()) {
    for (const piece of row) {
      if (piece?.type === 'k' && piece.color === turn) return piece.square
    }
  }
  return null
}
