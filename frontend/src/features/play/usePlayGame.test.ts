import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GameState } from '../../api/games'
import { gameState } from '../../test/factories'
import { thinkDelay, usePlayGame } from './usePlayGame'

const THINK = { min_s: 1, max_s: 1 } // no randomness: always 1 s
const START = gameState({ bot_think: THINK })
const AFTER_E4_E5 = gameState({
  bot_think: THINK,
  fen: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2',
  moves: [
    { ply: 0, uci: 'e2e4', san: 'e4', by_bot: false },
    { ply: 1, uci: 'e7e5', san: 'e5', by_bot: true },
  ],
  move_count: 2,
})

/** fetch stub: GET returns `game`, POST /moves returns `reply` after `delayMs` (fake time). */
function stubFetch(game: GameState, reply: GameState = AFTER_E4_E5, delayMs = 0) {
  vi.stubGlobal(
    'fetch',
    vi.fn((_: string, init?: RequestInit) => {
      const body = init?.method === 'POST' ? reply : game
      const response = () => new Response(JSON.stringify(body), { status: 200 })
      if (delayMs === 0 || init?.method !== 'POST') return Promise.resolve(response())
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve(response())
        }, delayMs)
      })
    }),
  )
}

/** Let pending promises (the fetch stubs) settle without moving fake time. */
async function flush() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}

describe('thinkDelay', () => {
  it('waits for a random time in the range, minus what the request took', () => {
    expect(thinkDelay({ min_s: 0.8, max_s: 1.8 }, 300, () => 0.5)).toBe(1000)
    expect(thinkDelay({ min_s: 0.8, max_s: 1.8 }, 2000, () => 1)).toBe(0)
    expect(thinkDelay(null, 0)).toBe(0)
  })
})

describe('usePlayGame: the bot "thinks" at least its minimum', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows the user move at once and the reply only after the minimum', async () => {
    stubFetch(START)
    const { result } = renderHook(() => usePlayGame(7))
    await flush()
    expect(result.current.game).not.toBeNull()
    act(() => {
      result.current.move('e2e4')
    })
    expect(result.current.fen).toContain('4P3') // the user's move is on the board
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0) // the response arrives (immediately)
    })
    expect(result.current.thinking).toBe(true)
    expect(result.current.busy).toBe('move') // the board cannot be moved
    expect(result.current.game?.moves.map((m) => m.san)).toEqual(['e4'])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(999)
    })
    expect(result.current.game?.moves).toHaveLength(1) // not yet
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(result.current.game?.moves.map((m) => m.san)).toEqual(['e4', 'e5'])
    expect(result.current.thinking).toBe(false)
    expect(result.current.busy).toBeNull()
  })

  it('adds nothing when the engine already took longer than the minimum', async () => {
    stubFetch(START, AFTER_E4_E5, 1500)
    const { result } = renderHook(() => usePlayGame(7))
    await flush()
    expect(result.current.game).not.toBeNull()
    act(() => {
      result.current.move('e2e4')
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })
    expect(result.current.thinking).toBe(false)
    expect(result.current.game?.moves).toHaveLength(2)
  })

  const BOT_OPENS = gameState({
    bot_think: { min_s: 0.8, max_s: 1.6 },
    player_color: 'black',
    fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
    turn: 'black',
    moves: [{ ply: 0, uci: 'e2e4', san: 'e4', by_bot: true }],
    move_count: 1,
  })

  it('a fresh game where the bot opens waits only the minimum', async () => {
    stubFetch(BOT_OPENS)
    const { result } = renderHook(() => usePlayGame(7, Date.now()))
    await flush()
    expect(result.current.game).not.toBeNull()
    expect(result.current.game?.moves).toHaveLength(0)
    expect(result.current.fen).toBe(BOT_OPENS.initial_fen)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(799)
    })
    expect(result.current.game?.moves).toHaveLength(0)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(result.current.game?.moves).toHaveLength(1)
  })

  it('no wait when reloading a game', async () => {
    stubFetch(BOT_OPENS)
    const { result } = renderHook(() => usePlayGame(7))
    await flush()
    expect(result.current.game?.moves).toHaveLength(1)
    expect(result.current.thinking).toBe(false)
  })
})
