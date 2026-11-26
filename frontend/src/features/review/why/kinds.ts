import type { Classification, Explanation, MoveReview } from '../../../api/analysis'

const REFUTATION: ReadonlySet<Classification> = new Set([
  'excellent',
  'good',
  'inaccuracy',
  'mistake',
  'blunder',
  'miss',
])
const TRY: ReadonlySet<Classification> = new Set(['inaccuracy', 'mistake', 'blunder', 'miss'])

/** "Pruébalo tú" is offered on ?!, ?, ?? and ✗. */
export function canTry(move: MoveReview): boolean {
  return TRY.has(move.classification)
}

/** Which replay a move offers: the refutation (not the best), the idea (!, !!, ★ explained). */
export function whyKindOf(
  move: MoveReview,
  explanation: Explanation | null,
): 'refutation' | 'idea' | null {
  if (REFUTATION.has(move.classification)) return 'refutation'
  if (move.classification === 'great' || move.classification === 'brilliant') return 'idea'
  if (move.classification === 'best' && explanation?.idea) return 'idea'
  return null
}
