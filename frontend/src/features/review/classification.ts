import type { Classification, WhiteEval } from '../../api/analysis'

export interface ClassMeta {
  label: string
  /** Short mark shown on badges ("!!", "?", "★"...). */
  mark: string
  color: string
}

export const CLASSIFICATIONS: Record<Classification, ClassMeta> = {
  brilliant: { label: 'Brillante', mark: '!!', color: '#1baca6' },
  great: { label: 'Gran jugada', mark: '!', color: '#5c8bb0' },
  best: { label: 'Mejor', mark: '★', color: '#81b64c' },
  excellent: { label: 'Excelente', mark: '👍', color: '#96bc4b' },
  good: { label: 'Buena', mark: '✓', color: '#95af8a' },
  book: { label: 'Teoría', mark: '📖', color: '#a88865' },
  inaccuracy: { label: 'Imprecisión', mark: '?!', color: '#f7c045' },
  mistake: { label: 'Error', mark: '?', color: '#e58f2a' },
  blunder: { label: 'Grave error', mark: '??', color: '#ca3431' },
  miss: { label: 'Oportunidad perdida', mark: '✗', color: '#ee6b55' },
}

/** Order used in summaries: from the best to the worst. */
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

/** "+1.3", "-0.4", "M3", "-M2" (white's point of view). */
export function evalLabel(e: WhiteEval): string {
  if (e.mate !== null) return e.mate > 0 ? `M${String(e.mate)}` : `-M${String(-e.mate)}`
  if (e.cp === null) return e.win === 50 ? '½' : e.win > 50 ? '1-0' : '0-1'
  const pawns = e.cp / 100
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(1)}`
}

/** "12." for white's 12th move, "12…" for black's. */
export function moveNumber(ply: number): string {
  return `${String(Math.floor(ply / 2) + 1)}${ply % 2 === 0 ? '.' : '…'}`
}
