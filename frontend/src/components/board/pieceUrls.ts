import type { PieceSet } from '../../api/ui'

/**
 * Piece sets (each with its licence in assets/pieces/<set>/LICENSE.md). Keys: "wK", "bP"...
 * The set is chosen in Ajustes (phase 6.5).
 */
const FILES = import.meta.glob<string>('../../assets/pieces/*/*.svg', {
  eager: true,
  query: '?url',
  import: 'default',
})

const SETS: Partial<Record<PieceSet, Record<string, string>>> = {}
for (const [path, url] of Object.entries(FILES)) {
  const match = /pieces\/([^/]+)\/(\w+)\.svg$/.exec(path)
  if (!match) continue
  const [, set, code] = match as unknown as [string, PieceSet, string]
  ;(SETS[set] ??= {})[code] = url
}

export const PIECE_CODES = ['wK', 'wQ', 'wR', 'wB', 'wN', 'wP', 'bK', 'bQ', 'bR', 'bB', 'bN', 'bP']

/** URL of a piece of a set (cburnett if the set lacks it). */
export function pieceUrl(code: string, set: PieceSet): string {
  return SETS[set]?.[code] ?? SETS.cburnett?.[code] ?? ''
}
