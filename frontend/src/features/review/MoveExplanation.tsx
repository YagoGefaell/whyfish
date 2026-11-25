import type { MoveReview } from '../../api/analysis'
import { CLASSIFICATIONS } from './classification'

/**
 * Slot for the move's explanation. Phase 4 fills it with template explanations (level 1 always
 * visible, level 2 behind "Profundizar"); for now it shows a provisional text.
 */
export function MoveExplanation({ move }: { move: MoveReview }) {
  const label = CLASSIFICATIONS[move.classification].label.toLowerCase()
  return (
    <p aria-label="Explicación" className="text-[15px] leading-relaxed text-muted">
      Pronto verás aquí por qué esta jugada es «{label}» y qué idea había detrás.
    </p>
  )
}
