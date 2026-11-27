import { request } from './client'
import type { Color, TimeClass } from './games'

/** A position that explains a figure: opens the review at that move. */
export interface StatExample {
  game_id: number
  ply: number
  san: string
  classification: string
  delta: number
  date: string
  opponent: string | null
}

export interface AccuracyPoint {
  game_id: number
  date: string
  accuracy: number
  average: number
}

export interface PhaseStat {
  phase: 'opening' | 'middlegame' | 'endgame'
  label: string
  moves: number
  errors: number
  per10: number
  examples: StatExample[]
}

export interface KindStat {
  kind: string
  label: string
  count: number
  mean_delta: number
  examples: StatExample[]
}

export interface OpeningStat {
  color: Color
  family: string
  games: number
  wins: number
  draws: number
  losses: number
  score: number
  accuracy: number | null
  worst: boolean
  game_ids: number[]
}

export interface TimeStat {
  games_with_clock: number
  low_moves: number
  low_errors: number
  normal_moves: number
  normal_errors: number
  low_rate: number | null
  normal_rate: number | null
  stands_out: boolean
  examples: StatExample[]
}

export interface WeakPoint {
  key: string
  title: string
  text: string
  advice: string
  cost: number
  examples: StatExample[]
  /** Filter to train these positions (phase 6c). */
  train: Record<string, string>
}

export interface Stats {
  games: number
  enough: boolean
  min_games: number
  accuracy_mean: number | null
  accuracy: AccuracyPoint[]
  phases: PhaseStat[]
  kinds: KindStat[]
  openings: OpeningStat[]
  time: TimeStat
  weak_points: WeakPoint[]
}

export interface StatsResponse {
  games_finished: number
  games_unanalysed: number
  insights_pending: number
  stats: Stats
}

export interface StatsFilters {
  include_bot?: boolean
  time_class?: TimeClass
  color?: Color
  days?: number
}

export const statsApi = {
  get: (filters: StatsFilters, signal?: AbortSignal) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined) params.set(key, String(value))
    }
    const query = params.toString()
    return request<StatsResponse>(`/stats${query ? `?${query}` : ''}`, { signal })
  },
}
