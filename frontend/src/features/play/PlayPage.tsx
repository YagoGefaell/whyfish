import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { gamesApi, type Color, type GameState } from '../../api/games'
import { Board } from '../../components/board/Board'
import { COLOR_LABEL, endText } from './gameText'
import { AnalyzeButton } from './AnalyzeButton'
import { MoveList } from './MoveList'
import { usePlayGame, type PlayGame } from './usePlayGame'

const BUTTON = 'btn'

export function PlayPage() {
  const { id } = useParams()
  const gameId = Number(id)
  if (!Number.isInteger(gameId) || gameId <= 0) {
    return <p className="text-danger">Partida no válida.</p>
  }
  return <PlayGameView key={gameId} gameId={gameId} />
}

function PlayGameView({ gameId }: { gameId: number }) {
  const play = usePlayGame(gameId)
  const [orientation, setOrientation] = useState<Color | null>(null)

  if (play.loadError) return <p className="text-danger">{play.loadError}</p>
  if (!play.game || !play.fen) return <p className="text-muted">Cargando partida…</p>

  const game = play.game
  if (game.source === 'imported') {
    return (
      <p>
        Esta partida es importada.{' '}
        <Link className="text-accent-strong underline" to={`/review/${String(game.id)}`}>
          Ver su revisión
        </Link>
      </p>
    )
  }
  const finished = game.status === 'finished'
  const playerTurn = !finished && game.turn === game.player_color
  const last = game.moves.at(-1)

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:justify-center">
      <div className="w-full min-w-0 lg:w-[min(calc(100vw-27rem),calc(100dvh-6.5rem))] lg:shrink-0">
        <Board
          fen={play.fen}
          orientation={orientation ?? game.player_color}
          playerColor={game.player_color}
          interactive={playerTurn && play.busy === null}
          lastMove={last ? { from: last.uci.slice(0, 2), to: last.uci.slice(2, 4) } : null}
          hintSquare={play.hintSquare}
          onMove={play.move}
        />
      </div>
      <aside className="panel flex min-w-0 flex-col gap-4 self-start p-4 lg:w-[360px] lg:shrink-0">
        <header>
          <h2 className="text-lg font-semibold">
            Tú ({COLOR_LABEL[game.player_color]}) vs Stockfish · {game.bot_level_label}
          </h2>
          <StatusLine game={game} busy={play.busy} />
          {play.notice && <p className="text-sm text-[#f7c631]">{play.notice}</p>}
          {play.actionError && (
            <p role="alert" className="text-sm text-danger">
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
      <p className="font-medium text-accent-strong">
        {endText(game.result, game.termination, game.player_color)}
      </p>
    )
  }
  if (busy === 'move' || game.turn !== game.player_color) {
    return <p className="text-muted">Stockfish está pensando…</p>
  }
  return <p className="text-accent-strong">Te toca ({COLOR_LABEL[game.player_color]})</p>
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
              className={`${BUTTON} border-danger text-danger`}
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
      {!ongoing && <AnalyzeButton game={game} />}
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
    <p className="text-sm text-muted">
      Ayudas usadas:
      {game.allow_undo && ` deshacer ${String(game.undo_count)}`}
      {game.allow_undo && game.allow_hint && ' ·'}
      {game.allow_hint && ` pistas ${String(game.hint_count)}`}
    </p>
  )
}
