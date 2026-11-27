import type { Classification, MoveReview, WhiteEval } from '../../api/analysis'

export interface ClassMeta {
  label: string
  /** Badge fill and square tint (the same in both modes). */
  color: string
  /** The verdict text ("es un error"), readable on the panels of the current mode. */
  textColor: string
  /** Coach sentence: `${san} ${phrase}` ("Nf3 es un error"). */
  phrase: string
  /** Badge in the move list (the board and the coach panel always show it). */
  inList: boolean
  /** An error of the mover: offers "Mostrar mejor jugada". */
  isError: boolean
}

export const CLASSIFICATIONS: Record<Classification, ClassMeta> = {
  brilliant: {
    label: 'Brillante',
    color: 'var(--color-cls-brilliant)',
    textColor: 'var(--color-cls-brilliant-text)',
    phrase: 'es brillante',
    inList: true,
    isError: false,
  },
  great: {
    label: 'Gran jugada',
    color: 'var(--color-cls-great)',
    textColor: 'var(--color-cls-great-text)',
    phrase: 'es una gran jugada',
    inList: true,
    isError: false,
  },
  best: {
    label: 'Mejor',
    color: 'var(--color-cls-best)',
    textColor: 'var(--color-cls-best-text)',
    phrase: 'es la mejor jugada',
    inList: false,
    isError: false,
  },
  excellent: {
    label: 'Excelente',
    color: 'var(--color-cls-excellent)',
    textColor: 'var(--color-cls-excellent-text)',
    phrase: 'es excelente',
    inList: false,
    isError: false,
  },
  good: {
    label: 'Buena',
    color: 'var(--color-cls-good)',
    textColor: 'var(--color-cls-good-text)',
    phrase: 'es buena',
    inList: false,
    isError: false,
  },
  book: {
    label: 'Teoría',
    color: 'var(--color-cls-book)',
    textColor: 'var(--color-cls-book-text)',
    phrase: 'es teoría',
    inList: false,
    isError: false,
  },
  inaccuracy: {
    label: 'Imprecisión',
    color: 'var(--color-cls-inaccuracy)',
    textColor: 'var(--color-cls-inaccuracy-text)',
    phrase: 'es una imprecisión',
    inList: true,
    isError: true,
  },
  mistake: {
    label: 'Error',
    color: 'var(--color-cls-mistake)',
    textColor: 'var(--color-cls-mistake-text)',
    phrase: 'es un error',
    inList: true,
    isError: true,
  },
  blunder: {
    label: 'Grave error',
    color: 'var(--color-cls-blunder)',
    textColor: 'var(--color-cls-blunder-text)',
    phrase: 'es un grave error',
    inList: true,
    isError: true,
  },
  miss: {
    label: 'Oportunidad perdida',
    color: 'var(--color-cls-miss)',
    textColor: 'var(--color-cls-miss-text)',
    phrase: 'es una oportunidad perdida',
    inList: true,
    isError: true,
  },
}

/** Order used in the summary table: from the best to the worst. */
export const CLASS_ORDER: Classification[] = [
  'brilliant',
  'great',
  'best',
  'excellent',
  'good',
  'book',
  'inaccuracy',
  'mistake',
  'blunder',
  'miss',
]

/** Dots on the evaluation graph. */
export const GRAPH_MARKED: ReadonlySet<Classification> = new Set([
  'brilliant',
  'mistake',
  'blunder',
  'miss',
])

/** "+1.3", "-0.4", "M3", "-M2" (white's point of view). */
export function evalLabel(e: WhiteEval): string {
  if (e.mate !== null) return e.mate > 0 ? `M${String(e.mate)}` : `-M${String(-e.mate)}`
  if (e.cp === null) return e.win === 50 ? '½-½' : e.win > 50 ? '1-0' : '0-1'
  const pawns = e.cp / 100
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(1)}`
}

/** "12." for white's 12th move, "12…" for black's. */
export function moveNumber(ply: number): string {
  return `${String(Math.floor(ply / 2) + 1)}${ply % 2 === 0 ? '.' : '…'}`
}

/** Moves that are (as good as) the engine's choice: no alternative is shown. */
const TOP_MOVES: ReadonlySet<Classification> = new Set(['best', 'great', 'brilliant', 'book'])

/** The move played was not the engine's best: show "La mejor era X" + arrow (SPEC §1.3). */
export function showsAlternative(move: MoveReview): boolean {
  return !TOP_MOVES.has(move.classification) && move.best_san !== null && move.best_uci !== move.uci
}
