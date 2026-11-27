import { useSyncExternalStore } from 'react'
import { uiApi, type BoardTheme, type PieceSet, type UiSettings } from '../api/ui'

/**
 * Interface preferences (phase 6.5): colour mode, board and piece set. Stored in the backend
 * (Ajustes); a copy in localStorage paints the right colours before the API answers. Applying
 * them sets `data-mode` and `data-board` on <html> (the tokens in tokens.css follow) and
 * re-renders the boards (usePrefs), which need the piece set and literal arrow colours.
 */

export const BOARDS: readonly BoardTheme[] = ['brown', 'blue', 'gray', 'wood', 'slate']
export const PIECE_SETS: readonly PieceSet[] = ['cburnett', 'mpchess', 'chessnut', 'rhosgfx']

export const BOARD_LABEL: Record<BoardTheme, string> = {
  brown: 'Marrón clásico',
  blue: 'Azul',
  gray: 'Gris',
  wood: 'Madera clara',
  slate: 'Pizarra',
}

export const PIECE_LABEL: Record<PieceSet, string> = {
  cburnett: 'Cburnett',
  mpchess: 'MPChess',
  chessnut: 'Chessnut',
  rhosgfx: 'RhosGFX',
}

export const DEFAULT_PREFS: UiSettings = {
  color_mode: 'system',
  board: 'brown',
  pieces: 'cburnett',
}

const CACHE_KEY = 'whyfish-ui'
const LIGHT_QUERY = '(prefers-color-scheme: light)'

let current: UiSettings = DEFAULT_PREFS
const listeners = new Set<() => void>()

function systemIsLight(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(LIGHT_QUERY).matches
}

function apply(): void {
  const root = document.documentElement
  const light =
    current.color_mode === 'light' || (current.color_mode === 'system' && systemIsLight())
  root.dataset.mode = light ? 'light' : 'dark'
  root.dataset.board = current.board
}

function valid(value: unknown): value is UiSettings {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    ['system', 'light', 'dark'].includes(String(v.color_mode)) &&
    BOARDS.includes(v.board as BoardTheme) &&
    PIECE_SETS.includes(v.pieces as PieceSet)
  )
}

function readCache(): UiSettings | null {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(CACHE_KEY) ?? 'null')
    return valid(parsed) ? parsed : null
  } catch {
    return null
  }
}

/** Applies preferences now (all boards re-render) and caches them for the next load. */
export function setPrefs(next: UiSettings): void {
  current = next
  apply()
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(next))
  } catch {
    // Storage blocked: the backend still has them.
  }
  for (const listener of listeners) listener()
}

/** Applies the cached preferences, then the backend's; follows the system colour scheme. */
export function initPrefs(): void {
  current = readCache() ?? DEFAULT_PREFS
  apply()
  if (typeof window.matchMedia === 'function') {
    window.matchMedia(LIGHT_QUERY).addEventListener('change', () => {
      if (current.color_mode === 'system') apply()
    })
  }
  uiApi
    .get()
    .then(setPrefs)
    .catch(() => {
      // Backend unreachable: keep the cached ones.
    })
}

export function prefs(): UiSettings {
  return current
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The current preferences; the component re-renders when they change. */
export function usePrefs(): UiSettings {
  return useSyncExternalStore(subscribe, prefs)
}

/**
 * The value of a colour token, for the few places that need a literal colour instead of
 * `var(--…)` (SVG presentation attributes drawn by react-chessboard, such as arrows).
 */
export function token(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

/** `var(--name)` → its literal value (other colours unchanged). */
export function resolveColor(color: string): string {
  const match = /^var\((--[\w-]+)\)$/.exec(color)
  return match?.[1] ? token(match[1], '#888888') : color
}
