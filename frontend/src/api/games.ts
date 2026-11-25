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

export interface GameSummary {
  id: number
  created_at: string
  player_color: Color
  bot_level: BotLevel
  bot_level_label: string
  result: GameResult | null
  termination: Termination | null
  move_count: number
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
  pgnUrl: (id: number) => `/api/games/${String(id)}/pgn`,
}
