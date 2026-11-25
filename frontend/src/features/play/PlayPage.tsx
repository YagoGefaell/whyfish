import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { gamesApi, type Color, type GameState } from '../../api/games'
import { Board } from '../../components/board/Board'
import { COLOR_LABEL, endText } from './gameText'
import { MoveList } from './MoveList'
import { usePlayGame, type PlayGame } from './usePlayGame'

const BUTTON =
  'rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50'

export function PlayPage() {
  const { id } = useParams()
  const gameId = Number(id)
  if (!Number.isInteger(gameId) || gameId <= 0) {
    return <p className="text-red-600">Partida no válida.</p>
  }
  return <PlayGameView key={gameId} gameId={gameId} />
}

function PlayGameView({ gameId }: { gameId: number }) {
  const play = usePlayGame(gameId)
  const [orientation, setOrientation] = useState<Color | null>(null)

  if (play.loadError) return <p className="text-red-600">{play.loadError}</p>
  if (!play.game || !play.fen) return <p className="text-gray-500">Cargando partida…</p>

  const game = play.game
  const finished = game.status === 'finished'
  const playerTurn = !finished && game.turn === game.player_color
  const last = game.moves.at(-1)

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <Board
        fen={play.fen}
        orientation={orientation ?? game.player_color}
        playerColor={game.player_color}
        interactive={playerTurn && play.busy === null}
        lastMove={last ? { from: last.uci.slice(0, 2), to: last.uci.slice(2, 4) } : null}
        hintSquare={play.hintSquare}
        onMove={play.move}
      />
      <aside className="flex min-w-64 flex-1 flex-col gap-4">
        <header>
          <h2 className="text-lg font-semibold">
            Tú ({COLOR_LABEL[game.player_color]}) vs Stockfish · {game.bot_level_label}
          </h2>
          <StatusLine game={game} busy={play.busy} />
          {play.notice && <p className="text-sm text-amber-700">{play.notice}</p>}
          {play.actionError && (
            <p role="alert" className="text-sm text-red-600">
              {play.actionError}
            </p>
          )}
        </header>
        <MoveList moves={game.moves} initialFen={game.initial_fen} />
        <Controls
          play={play}
          game={game}
          onFlip={() => {
            setOrientation((o) => {
              const current = o ?? game.player_color
              return current === 'white' ? 'black' : 'white'
            })
          }}
        />
        <AssistsUsed game={game} />
      </aside>
    </div>
  )
}

function StatusLine({ game, busy }: { game: GameState; busy: PlayGame['busy'] }) {
  if (game.status === 'finished' && game.result) {
    return (
      <p className="font-medium text-blue-800">
        {endText(game.result, game.termination, game.player_color)}
      </p>
    )
  }
  if (busy === 'move' || game.turn !== game.player_color) {
    return <p className="text-gray-600">Stockfish está pensando…</p>
  }
  return <p className="text-green-700">Te toca ({COLOR_LABEL[game.player_color]})</p>
}

function Controls({ play, game, onFlip }: { play: PlayGame; game: GameState; onFlip: () => void }) {
  const [confirmResign, setConfirmResign] = useState(false)
  const ongoing = game.status === 'ongoing'
  const idle = play.busy === null
  const playerTurn = ongoing && game.turn === game.player_color

  return (
    <div className="flex flex-wrap gap-2">
      <button type="button" className={BUTTON} onClick={onFlip}>
        Girar tablero
      </button>
      {game.allow_undo && ongoing && (
        <button type="button" className={BUTTON} disabled={!idle} onClick={play.undo}>
          Deshacer
        </button>
      )}
      {game.allow_hint && ongoing && (
        <button
          type="button"
          className={BUTTON}
          disabled={!idle || !playerTurn}
          onClick={play.hint}
        >
          Pista
        </button>
      )}
      {ongoing && (
        <button type="button" className={BUTTON} disabled={!idle} onClick={play.offerDraw}>
          Ofrecer tablas
        </button>
      )}
      {ongoing &&
        (confirmResign ? (
          <span className="flex items-center gap-2 text-sm">
            ¿Abandonar?
            <button
              type="button"
              className={`${BUTTON} border-red-400 text-red-700`}
              disabled={!idle}
              onClick={() => {
                setConfirmResign(false)
                play.resign()
              }}
            >
              Sí, abandonar
            </button>
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                setConfirmResign(false)
              }}
            >
              No
            </button>
          </span>
        ) : (
          <button
            type="button"
            className={BUTTON}
            disabled={!idle}
            onClick={() => {
              setConfirmResign(true)
            }}
          >
            Abandonar
          </button>
        ))}
      <a className={BUTTON} href={gamesApi.pgnUrl(game.id)} download>
        Descargar PGN
      </a>
      {!ongoing && (
        <Link className={BUTTON} to="/">
          Nueva partida
        </Link>
      )}
    </div>
  )
}

function AssistsUsed({ game }: { game: GameState }) {
  if (!game.allow_undo && !game.allow_hint) return null
  return (
    <p className="text-sm text-gray-500">
      Ayudas usadas:
      {game.allow_undo && ` deshacer ${String(game.undo_count)}`}
      {game.allow_undo && game.allow_hint && ' ·'}
      {game.allow_hint && ` pistas ${String(game.hint_count)}`}
    </p>
  )
}
