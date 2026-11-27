import type { Explanation, TryResult } from './analysis'
import { request } from './client'
import type { Color } from './games'

export interface TrainingPosition {
  position: number
  item_id: number
  state: 'pending' | 'correct' | 'wrong'
  /** A failed exercise coming back at the end of the session. */
  repeat: boolean
}

export interface TrainingSession {
  id: number
  /** Counts for the streak; false = filtered (from a weak point). */
  daily: boolean
  filter: Record<string, string | boolean>
  positions: TrainingPosition[]
  /** First position without an answer; null = finished. */
  current: number | null
  correct: number
  answered: number
  completed: boolean
  streak: number
  counts: Record<string, number>
}

export interface Exercise {
  id: number
  kind: 'miss' | 'error'
  prompt: string
  fen: string
  /** The opponent's last move (UCI), highlighted for a ✗. */
  last_move: string | null
  context: {
    opponent: string
    origin: string
    pace: string | null
    move_number: number
    color: Color
  }
  error_kind: string | null
  phase: string
  low_time: boolean | null
}

export interface TrainingAttempt {
  result: TryResult
  /** What the best move achieved (level 1), when right. */
  explanation: Explanation | null
  game_id: number
  ply: number
  external_url: string | null
  box: number
  due_on: string | null
  learned: boolean
  counted: boolean
  session: TrainingSession
}

export interface TrainingSettings {
  session_size: number
  weak_new: number
  include_bullet: boolean
}

export interface TrainingFilter {
  error_kind?: string
  phase?: string
  low_time?: boolean
}

const send = <T>(method: 'POST' | 'PUT', path: string, body: unknown) =>
  request<T>(path, { method, body: JSON.stringify(body) })

export const trainingApi = {
  session: (filter: TrainingFilter) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filter)) {
      if (value !== undefined) params.set(key, String(value))
    }
    const query = params.toString()
    return request<TrainingSession>(`/training/session${query ? `?${query}` : ''}`)
  },
  exercise: (itemId: number) => request<Exercise>(`/training/items/${String(itemId)}`),
  attempt: (sessionId: number, position: number, uci: string) =>
    send<TrainingAttempt>(
      'POST',
      `/training/sessions/${String(sessionId)}/positions/${String(position)}/attempt`,
      { uci },
    ),
  settings: () => request<TrainingSettings>('/training/settings'),
  saveSettings: (s: TrainingSettings) => send<TrainingSettings>('PUT', '/training/settings', s),
}
