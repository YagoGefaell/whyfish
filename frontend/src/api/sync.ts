import { request } from './client'
import type { Platform } from './games'

export interface Account {
  platform: Platform
  username: string
  /** Games from here to `newest_at` are imported. */
  covered_from: string | null
  newest_at: string | null
  last_synced_at: string | null
  last_error: string | null
  imported_count: number
}

export interface Accounts {
  accounts: Account[]
  /** How far back the first sync (and each "older games" step) goes. */
  sync_months: number
}

export interface AccountProgress {
  platform: Platform
  username: string
  state: 'waiting' | 'running' | 'done' | 'error'
  imported: number
  skipped: number
  error: string | null
}

export interface SyncState {
  running: boolean
  older: boolean
  accounts: AccountProgress[]
  finished_at: string | null
}

export interface QueueState {
  enabled: boolean
  paused: boolean
  /** Synchronised games still to analyse (including the current one). */
  pending: number
  current_game_id: number | null
  failed: number
}

const send = <T>(method: 'POST' | 'PUT', path: string, body?: unknown) =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) })

export const syncApi = {
  accounts: () => request<Accounts>('/accounts'),
  saveAccounts: (lichess: string, chesscom: string) =>
    send<Accounts>('PUT', '/accounts', { lichess, chesscom }),
  state: () => request<SyncState>('/sync'),
  start: (older = false) => send<SyncState>('POST', '/sync', { older }),
  queue: () => request<QueueState>('/queue'),
  pause: () => send<QueueState>('POST', '/queue/pause'),
  resume: () => send<QueueState>('POST', '/queue/resume'),
}
