import type { Color, GameResult, Termination } from '../../api/games'

export const COLOR_LABEL: Record<Color, string> = { white: 'blancas', black: 'negras' }

const TERMINATION_TEXT: Record<Termination, string> = {
  checkmate: 'por jaque mate',
  stalemate: 'por ahogado',
  insufficient_material: 'por material insuficiente',
  threefold_repetition: 'por triple repetición',
  fifty_moves: 'por la regla de las 50 jugadas',
  resignation: 'por abandono',
  draw_agreed: 'por acuerdo',
}

export type PlayerOutcome = 'win' | 'loss' | 'draw'

export function playerOutcome(result: GameResult, playerColor: Color): PlayerOutcome {
  if (result === '1/2-1/2') return 'draw'
  const whiteWon = result === '1-0'
  return whiteWon === (playerColor === 'white') ? 'win' : 'loss'
}

const OUTCOME_TEXT: Record<PlayerOutcome, string> = {
  win: 'Has ganado',
  loss: 'Has perdido',
  draw: 'Tablas',
}

export function outcomeShortText(result: GameResult | null, playerColor: Color): string {
  return result === null ? 'En curso' : OUTCOME_TEXT[playerOutcome(result, playerColor)]
}

export function endText(
  result: GameResult,
  termination: Termination | null,
  playerColor: Color,
): string {
  const base = OUTCOME_TEXT[playerOutcome(result, playerColor)]
  return termination === null ? base : `${base} ${TERMINATION_TEXT[termination]}`
}

/** Group plies into numbered rows: [[1, 'e4', 'e5'], [2, 'Nf3', undefined]]. */
export function moveRows(sans: string[]): [number, string, string][] {
  const rows: [number, string, string][] = []
  for (let i = 0; i < sans.length; i += 2) {
    rows.push([i / 2 + 1, sans[i] ?? '', sans[i + 1] ?? ''])
  }
  return rows
}
