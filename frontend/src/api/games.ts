import { request } from './client'

export type Color = 'white' | 'black'
export type ColorChoice = Color | 'random'
export type BotLevel = 'beginner' | 'novice' | 'club' | 'strong' | 'max'
export type Termination =
  | 'checkmate'
  | 'stalemate'
  | 'insufficient_material'
  | 'threefold_repetition'
  | 'fifty_moves'
  | 'resignation'
  | 'draw_agreed'
export type GameResult = '1-0' | '0-1' | '1/2-1/2'

export interface Level {
  id: BotLevel
  label: string
}

export interface MoveRecord {
  ply: number
  uci: string
  san: string
  by_bot: boolean
}

export type GameSource = 'played' | 'imported'
export type AnalysisStatus = 'pending' | 'running' | 'done' | 'failed'

export interface GameSummary {
  id: number
  created_at: string
  source: GameSource
  /** The user's color (for imported games: chosen or detected). */
  player_color: Color
  bot_level: BotLevel | null
  bot_level_label: string | null
  white_name: string | null
  black_name: string | null
  event: string | null
  played_date: string | null
  /** '*' = unknown result of an imported game. */
  result: GameResult | '*' | null
  termination: Termination | null
  move_count: number
  analysis_status: AnalysisStatus | null
}

export interface GameState extends GameSummary {
  status: 'ongoing' | 'finished'
  initial_fen: string
  fen: string
  turn: Color
  moves: MoveRecord[]
  allow_undo: boolean
  allow_hint: boolean
  undo_count: number
  hint_count: number
}

export interface NewGame {
  color: ColorChoice
  level: BotLevel
  allow_undo: boolean
  allow_hint: boolean
  /** Optional start position; null means the standard start. */
  fen: string | null
}

export interface DrawOffer {
  accepted: boolean
  declined_reason: 'too_early' | 'position' | null
  min_moves: number
  game: GameState
}

export interface ImportResult {
  game: GameState
  warnings: string[]
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const gamesApi = {
  levels: () => request<Level[]>('/levels'),
  list: () => request<GameSummary[]>('/games'),
  get: (id: number) => request<GameState>(`/games/${String(id)}`),
  create: (body: NewGame) => post<GameState>('/games', body),
  move: (id: number, uci: string) => post<GameState>(`/games/${String(id)}/moves`, { uci }),
  undo: (id: number) => post<GameState>(`/games/${String(id)}/undo`),
  hint: (id: number) => post<{ square: string }>(`/games/${String(id)}/hint`),
  resign: (id: number) => post<GameState>(`/games/${String(id)}/resign`),
  offerDraw: (id: number) => post<DrawOffer>(`/games/${String(id)}/draw`),
  importPgn: (pgn: string, userColor: Color | null) =>
    post<ImportResult>('/games/import', { pgn, user_color: userColor }),
  pgnUrl: (id: number) => `/api/games/${String(id)}/pgn`,
}
