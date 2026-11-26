import type { GameState } from '../api/games'

export function gameState(overrides: Partial<GameState> = {}): GameState {
  return {
    id: 7,
    created_at: '2026-11-25T10:00:00Z',
    source: 'played',
    white_name: null,
    black_name: null,
    event: null,
    played_date: null,
    analysis_status: null,
    player_color: 'white',
    bot_level: 'club',
    bot_level_label: 'Club ~1500',
    result: null,
    termination: null,
    move_count: 0,
    status: 'ongoing',
    initial_fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    turn: 'white',
    moves: [],
    allow_undo: false,
    allow_hint: false,
    undo_count: 0,
    hint_count: 0,
    bot_think: { min_s: 0, max_s: 0 },
    ...overrides,
  }
}
