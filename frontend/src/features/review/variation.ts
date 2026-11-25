import { Chess } from 'chess.js'

/** FEN of every position of the main line: start + after each move. */
export function mainLineFens(initialFen: string, ucis: string[]): string[] {
  const chess = new Chess(initialFen)
  const fens = [chess.fen()]
  for (const uci of ucis) {
    chess.move(uciToMove(uci))
    fens.push(chess.fen())
  }
  return fens
}

export function uciToMove(uci: string): { from: string; to: string; promotion?: string } {
  const promotion = uci.slice(4)
  return { from: uci.slice(0, 2), to: uci.slice(2, 4), ...(promotion ? { promotion } : {}) }
}

/** FEN after playing `ucis` from `fen` (assumed legal). */
export function fenAfter(fen: string, ucis: string[]): string {
  const chess = new Chess(fen)
  for (const uci of ucis) chess.move(uciToMove(uci))
  return chess.fen()
}

/** SAN moves -> UCI, from `fen`. Stops at the first move that does not parse. */
export function sansToUcis(fen: string, sans: string[]): string[] {
  const chess = new Chess(fen)
  const ucis: string[] = []
  for (const san of sans) {
    try {
      const move = chess.move(san)
      ucis.push(move.from + move.to + (move.promotion ?? ''))
    } catch {
      break
    }
  }
  return ucis
}

/** SAN of `ucis` played from `fen`. */
export function ucisToSans(fen: string, ucis: string[]): string[] {
  const chess = new Chess(fen)
  return ucis.map((uci) => chess.move(uciToMove(uci)).san)
}

/** Fullmove number and side to move of a FEN. */
export function fenStart(fen: string): { moveNumber: number; blackToMove: boolean } {
  const parts = fen.split(' ')
  return { moveNumber: Number.parseInt(parts[5] ?? '1', 10) || 1, blackToMove: parts[1] === 'b' }
}
