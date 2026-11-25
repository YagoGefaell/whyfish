import { useCallback, useEffect, useState } from 'react'
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

/** Game state for /play/:id. Everything is loaded from the server, so a reload restores it. */
export function usePlayGame(gameId: number): PlayGame {
  const [game, setGame] = useState<GameState | null>(null)
  const [optimisticFen, setOptimisticFen] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState<BusyAction | null>(null)
  const [hintSquare, setHintSquare] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    gamesApi
      .get(gameId)
      .then((state) => {
        if (!cancelled) setGame(state)
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(message(error))
      })
    return () => {
      cancelled = true
    }
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
      if (!game) return
      setOptimisticFen(applyUci(game.fen, uci))
      setHintSquare(null)
      run('move', () => gamesApi.move(gameId, uci))
    },
    [game, gameId, run],
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
      const { accepted, game: state } = await gamesApi.offerDraw(gameId)
      if (!accepted) setNotice('Stockfish rechaza las tablas.')
      return state
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
    move,
    undo,
    hint,
    resign,
    offerDraw,
  }
}
