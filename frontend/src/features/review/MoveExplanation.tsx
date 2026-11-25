import type { MoveReview } from '../../api/analysis'
import { CLASSIFICATIONS } from './classification'

/**
 * Slot for the move's explanation. Phase 4 fills it with template explanations (level 1 always
 * visible, level 2 behind "Profundizar"); for now it shows a provisional text.
 */
export function MoveExplanation({ move }: { move: MoveReview }) {
  const label = CLASSIFICATIONS[move.classification].label
  return (
    <section aria-label="Explicación" className="rounded border border-dashed border-gray-300 p-3">
      <h3 className="mb-1 text-sm font-semibold text-gray-700">Explicación</h3>
      <p className="text-sm text-gray-500">
        Pronto verás aquí por qué esta jugada es «{label}» y qué idea había detrás.
      </p>
    </section>
  )
}
