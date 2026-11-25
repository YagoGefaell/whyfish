import type { GameState } from '../../api/games'

/** Display names of both sides: PGN names for imported games, "Tú" / Stockfish otherwise. */
export function playerNames(game: GameState): { white: string; black: string } {
  if (game.source === 'imported') {
    return { white: game.white_name ?? 'Blancas', black: game.black_name ?? 'Negras' }
  }
  const bot = `Stockfish${game.bot_level_label ? ` (${game.bot_level_label})` : ''}`
  return game.player_color === 'white' ? { white: 'Tú', black: bot } : { white: bot, black: 'Tú' }
}
