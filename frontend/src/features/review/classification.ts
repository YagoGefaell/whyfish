import type { Classification, MoveReview, WhiteEval } from '../../api/analysis'

export interface ClassMeta {
  label: string
  color: string
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
    color: '#26c2a3',
    phrase: 'es brillante',
    inList: true,
    isError: false,
  },
  great: {
    label: 'Gran jugada',
    color: '#5c8bb0',
    phrase: 'es una gran jugada',
    inList: true,
    isError: false,
  },
  best: {
    label: 'Mejor',
    color: '#81b64c',
    phrase: 'es la mejor jugada',
    inList: false,
    isError: false,
  },
  excellent: {
    label: 'Excelente',
    color: '#81b64c',
    phrase: 'es excelente',
    inList: false,
    isError: false,
  },
  good: { label: 'Buena', color: '#95b776', phrase: 'es buena', inList: false, isError: false },
  book: { label: 'Teoría', color: '#a88865', phrase: 'es teoría', inList: false, isError: false },
  inaccuracy: {
    label: 'Imprecisión',
    color: '#f7c631',
    phrase: 'es una imprecisión',
    inList: true,
    isError: true,
  },
  mistake: { label: 'Error', color: '#ff9a3c', phrase: 'es un error', inList: true, isError: true },
  blunder: {
    label: 'Grave error',
    color: '#e5423a',
    phrase: 'es un grave error',
    inList: true,
    isError: true,
  },
  miss: {
    label: 'Oportunidad perdida',
    color: '#ee6b6b',
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
