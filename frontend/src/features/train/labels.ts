export const KIND_LABEL: Record<string, string> = {
  hanging: 'Pieza colgada',
  tactic_allowed: 'Táctica del rival no vista',
  allows_mate: 'Mate permitido',
  missed_mate: 'Mate no visto',
  missed_gain: 'Ganancia no vista',
  loses_material: 'Material perdido',
  positional: 'Sin causa táctica clara',
}

export const PHASE_LABEL: Record<string, string> = {
  opening: 'apertura',
  middlegame: 'medio juego',
  endgame: 'final',
}

/** "Pieza colgada · medio juego" for a session filter. */
export function filterLabel(filter: Record<string, string | boolean>): string {
  const parts: string[] = []
  if (typeof filter.error_kind === 'string')
    parts.push(KIND_LABEL[filter.error_kind] ?? filter.error_kind)
  if (typeof filter.phase === 'string') parts.push(PHASE_LABEL[filter.phase] ?? filter.phase)
  if (filter.low_time === true) parts.push('con poco tiempo')
  return parts.join(' · ')
}
