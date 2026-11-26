import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { gamesApi, type GameState } from '../../api/games'
import { applyUci } from '../../components/board/moves'

export type BusyAction = 'move' | 'undo' | 'hint' | 'resign' | 'draw'

export interface PlayGame {
  game: GameState | null
  /** FEN to display: optimistic while the server answers, else the server's. */
  fen: string | null
  loadError: string | null
  actionError: string | null
  busy: BusyAction | null
  hintSquare: string | null
  notice: string | null
  /** The bot's reply arrived but is held back for its minimum "thinking" time. */
  thinking: boolean
  move: (uci: string) => void
  undo: () => void
  hint: () => void
  resign: () => void
  offerDraw: () => void
}

function message(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'No se pudo contactar con el servidor.'
}

type ThinkRange = GameState['bot_think']

/**
 * How long to hold the bot's reply back (ms) so that it seems to think a random time within its
 * range: only what the request did not already take (SPEC §1.1).
 */
export function thinkDelay(range: ThinkRange, elapsedMs: number, random = Math.random): number {
  if (!range) return 0
  const target = (range.min_s + random() * (range.max_s - range.min_s)) * 1000
  return Math.max(0, Math.round(target - elapsedMs))
}

/** The state just before the bot's last move: shown while it "thinks". */
function beforeBotMove(state: GameState, fen: string): GameState {
  return {
    ...state,
    moves: state.moves.slice(0, -1),
    fen,
    turn: state.player_color === 'white' ? 'black' : 'white',
    status: 'ongoing',
    result: null,
    termination: null,
  }
}

/** A bot opening a game this fresh (ms) still "thinks"; older ones (a reload) never wait. */
const FRESH_MS = 15_000

/**
 * Game state for /play/:id. Everything is loaded from the server, so a reload restores it.
 * `createdAt` (Date.now() when the game was created, only right after creating it): if the bot
 * opens, its first move is shown after its minimum thinking time.
 */
export function usePlayGame(gameId: number, createdAt: number | null = null): PlayGame {
  const [game, setGame] = useState<GameState | null>(null)
  const [optimisticFen, setOptimisticFen] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState<BusyAction | null>(null)
  const [hintSquare, setHintSquare] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [thinking, setThinking] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  /** Show `state` now, or `interim` first and `state` after `wait` ms (the bot "thinking"). */
  const reveal = useCallback((state: GameState, interim: GameState, wait: number) => {
    if (wait <= 0) {
      setGame(state)
      setOptimisticFen(null)
      setBusy(null)
      return
    }
    setGame(interim)
    setOptimisticFen(null)
    setThinking(true)
    timer.current = window.setTimeout(() => {
      timer.current = null
      setGame(state)
      setThinking(false)
      setBusy(null)
    }, wait)
  }, [])

  useEffect(() => {
    let cancelled = false
    gamesApi
      .get(gameId)
      .then((state) => {
        if (cancelled) return
        const opening = state.moves.length === 1 && state.moves[0].by_bot
        const age = createdAt === null ? Infinity : Date.now() - createdAt
        if (opening && age < FRESH_MS && state.bot_think) {
          // Only the minimum, minus what creating and loading the game already took.
          const wait = Math.max(0, Math.round(state.bot_think.min_s * 1000 - age))
          if (wait > 0) setBusy('move')
          reveal(state, beforeBotMove(state, state.initial_fen), wait)
        } else {
          setGame(state)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(message(error))
      })
    return () => {
      cancelled = true
    }
    // createdAt is only read once, on load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  const run = useCallback(
    (action: BusyAction, call: () => Promise<GameState | null>) => {
      if (busy !== null) return
      setBusy(action)
      setActionError(null)
      setNotice(null)
      call()
        .then((state) => {
          if (state) setGame(state)
        })
        .catch((error: unknown) => {
          setActionError(message(error))
        })
        .finally(() => {
          setOptimisticFen(null)
          setBusy(null)
        })
    },
    [busy],
  )

  const move = useCallback(
    (uci: string) => {
      if (!game || busy !== null) return
      const shown = applyUci(game.fen, uci)
      if (shown === null) return
      const before = game.moves.length
      const started = Date.now()
      setOptimisticFen(shown)
      setHintSquare(null)
      setBusy('move')
      setActionError(null)
      setNotice(null)
      gamesApi
        .move(gameId, uci)
        .then((state) => {
          const botReplied = state.moves.length === before + 2 && state.moves.at(-1)?.by_bot
          const wait = botReplied ? thinkDelay(state.bot_think, Date.now() - started) : 0
          reveal(state, beforeBotMove(state, shown), wait)
        })
        .catch((error: unknown) => {
          setActionError(message(error))
          setOptimisticFen(null)
          setBusy(null)
        })
    },
    [game, gameId, busy, reveal],
  )

  const undo = useCallback(() => {
    setHintSquare(null)
    run('undo', () => gamesApi.undo(gameId))
  }, [gameId, run])

  const hint = useCallback(() => {
    run('hint', async () => {
      const { square } = await gamesApi.hint(gameId)
      setHintSquare(square)
      return gamesApi.get(gameId) // refresh hint_count
    })
  }, [gameId, run])

  const resign = useCallback(() => {
    run('resign', () => gamesApi.resign(gameId))
  }, [gameId, run])

  const offerDraw = useCallback(() => {
    run('draw', async () => {
      const offer = await gamesApi.offerDraw(gameId)
      if (offer.declined_reason === 'too_early') {
        setNotice(
          `Stockfish no acepta tablas hasta que se hayan jugado ${String(offer.min_moves)} jugadas.`,
        )
      } else if (offer.declined_reason === 'position') {
        setNotice('Stockfish rechaza las tablas.')
      }
      return offer.game
    })
  }, [gameId, run])

  return {
    game,
    fen: optimisticFen ?? game?.fen ?? null,
    loadError,
    actionError,
    busy,
    hintSquare,
    notice,
    thinking,
    move,
    undo,
    hint,
    resign,
    offerDraw,
  }
}
