import { request } from './client'

export type ColorMode = 'system' | 'light' | 'dark'
export type BoardTheme = 'brown' | 'blue' | 'gray' | 'wood' | 'slate'
export type PieceSet = 'cburnett' | 'mpchess' | 'chessnut' | 'rhosgfx'

/** Interface settings (phase 6.5), stored in the backend database. */
export interface UiSettings {
  color_mode: ColorMode
  board: BoardTheme
  pieces: PieceSet
}

export const uiApi = {
  get: () => request<UiSettings>('/settings/ui'),
  save: (s: UiSettings) =>
    request<UiSettings>('/settings/ui', { method: 'PUT', body: JSON.stringify(s) }),
}
