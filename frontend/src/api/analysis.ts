import { request } from './client'
import type { AnalysisStatus, Color } from './games'

export type Classification =
  | 'book'
  | 'brilliant'
  | 'great'
  | 'best'
  | 'excellent'
  | 'good'
  | 'inaccuracy'
  | 'mistake'
  | 'blunder'
  | 'miss'

export interface AnalysisJob {
  game_id: number
  status: AnalysisStatus
  done: number
  total: number
  error: string | null
}

/** Evaluation from white's point of view. */
export interface WhiteEval {
  win: number
  cp: number | null
  mate: number | null
}

export interface MoveReview {
  ply: number
  color: Color
  uci: string
  san: string
  classification: Classification
  symbol: string
  win_before: number
  win_after: number
  delta: number
  accuracy: number
  best_uci: string | null
  best_san: string | null
  /** SAN from the position before the move. */
  best_line: string[]
  /** SAN from the position after the move: the engine's continuation. */
  played_line: string[]
}

export interface PlayerSummary {
  accuracy: number | null
  counts: Record<Classification, number>
}

export interface Review {
  game_id: number
  perspective: Color
  opening: { eco: string; name: string } | null
  white: PlayerSummary
  black: PlayerSummary
  key_moments: number[]
  moves: MoveReview[]
  /** One per position: start + after each move. */
  evals: WhiteEval[]
}

export interface EvaluatedLine {
  uci: string[]
  san: string[]
  cp: number | null
  mate: number | null
  win: number
}

export interface Evaluation {
  fen: string
  turn: Color
  terminal: 'checkmate' | 'stalemate' | 'draw' | null
  lines: EvaluatedLine[]
  best_uci: string | null
  best_san: string | null
  white: WhiteEval
}

/** Where a [[SAN]] mark is shown: `path` (UCI) played from main-line position `base`. */
export interface MoveRef {
  san: string
  line: 'played' | 'best' | 'second'
  base: number
  path: string[]
}

/** Drawn on the position after the move: threat/danger in red, attack/target in amber. */
export interface Annotation {
  kind: 'arrow' | 'square'
  role: 'threat' | 'danger' | 'attack' | 'target'
  square: string | null
  from_square: string | null
  to_square: string | null
}

export interface Explanation {
  ply: number
  level: 1 | 2
  /** Moves marked as [[SAN]]; `refs` has one entry per mark, in order. null = nothing to say. */
  text: string | null
  refs: MoveRef[]
  annotations: Annotation[]
  idea: string | null
}

/** One step of "Ver por qué": the move, the position after it and what it does. */
export interface WhyStep {
  index: number
  label: string // "21…dxc3"
  san: string
  uci: string
  fen: string
  color: Color
  caption: string
  /** The user's best defence according to the engine (not what was played). */
  defense: boolean
  consequence: boolean
  arrows: { from_square: string; to_square: string }[]
}

/** "Ver por qué" / "Ver la idea": the sequence up to the consequence of a move. */
export interface Why {
  kind: 'refutation' | 'idea'
  tone: 'bad' | 'good'
  base_ply: number
  start_fen: string
  title: string
  alternative: string | null
  steps: WhyStep[]
  consequence_ply: number | null
  /** Moves marked as [[SAN]]; `refs` has one entry per mark. */
  summary: string
  refs: MoveRef[]
  step_ms: number
}

export type WhyKind = 'refutation' | 'idea' | 'solution'

/** "Pruébalo tú": the verdict on an attempt and, if it fails, why. */
export interface TryResult {
  uci: string
  san: string
  classification: Classification
  correct: boolean
  why: Why | null
}

const post = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
  request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })

export const analysisApi = {
  start: (gameId: number) => post<AnalysisJob>(`/games/${String(gameId)}/analysis`),
  status: (gameId: number) => request<AnalysisJob>(`/games/${String(gameId)}/analysis`),
  review: (gameId: number) => request<Review>(`/games/${String(gameId)}/review`),
  streamUrl: (gameId: number) => `/api/games/${String(gameId)}/analysis/stream`,
  explanation: (gameId: number, ply: number, level: 1 | 2, signal?: AbortSignal) =>
    request<Explanation>(
      `/games/${String(gameId)}/moves/${String(ply)}/explanation?level=${String(level)}`,
      { signal },
    ),
  evaluate: (fen: string, moves: string[], signal?: AbortSignal) =>
    post<Evaluation>('/analysis/evaluate', { fen, moves }, signal),
  why: (gameId: number, ply: number, kind: WhyKind, signal?: AbortSignal) =>
    request<Why>(`/games/${String(gameId)}/moves/${String(ply)}/why?kind=${kind}`, { signal }),
  tryMove: (gameId: number, ply: number, uci: string, signal?: AbortSignal) =>
    post<TryResult>(`/games/${String(gameId)}/moves/${String(ply)}/try`, { uci }, signal),
}
