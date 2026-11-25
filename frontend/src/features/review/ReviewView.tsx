import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Review } from '../../api/analysis'
import type { GameState } from '../../api/games'
import { CLASSIFICATIONS, evalLabel, moveNumber } from './classification'
import { EvalBar } from './EvalBar'
import { EvalGraph } from './EvalGraph'
import { MoveDetail } from './MoveDetail'
import { MoveTable } from './MoveTable'
import { playerNames } from './names'
import { ReviewBoard, type BoardArrow } from './ReviewBoard'
import { ReviewSummary } from './ReviewSummary'
import { useEvaluation } from './useEvaluation'
import { fenAfter, fenStart, mainLineFens, sansToUcis, ucisToSans } from './variation'

const BEST_ARROW = '#2f9e44'

interface Exploration {
  /** Main-line position the variation starts from. */
  base: number
  moves: string[] // UCI
  /** How many of `moves` are shown (0 = the base position). */
  index: number
}

type Tab = 'move' | 'moves' | 'summary'
const TABS: { id: Tab; label: string }[] = [
  { id: 'move', label: 'Jugada' },
  { id: 'moves', label: 'Jugadas' },
  { id: 'summary', label: 'Resumen' },
]

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

export function ReviewView({ game, review }: { game: GameState; review: Review }) {
  const fens = useMemo(
    () =>
      mainLineFens(
        game.initial_fen,
        review.moves.map((m) => m.uci),
      ),
    [game.initial_fen, review.moves],
  )
  const last = fens.length - 1
  const [position, setPosition] = useState(0)
  const [exploration, setExploration] = useState<Exploration | null>(null)
  const [tab, setTab] = useState<Tab>('move')
  const orientation = review.perspective

  const select = useCallback((p: number) => {
    setExploration(null)
    setPosition(p)
  }, [])

  const back = useCallback(() => {
    if (exploration) {
      if (exploration.index > 0) setExploration({ ...exploration, index: exploration.index - 1 })
      else select(exploration.base)
    } else setPosition((p) => Math.max(0, p - 1))
  }, [exploration, select])

  const forward = useCallback(() => {
    if (exploration) {
      setExploration({
        ...exploration,
        index: Math.min(exploration.moves.length, exploration.index + 1),
      })
    } else setPosition((p) => Math.min(last, p + 1))
  }, [exploration, last])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.altKey || event.ctrlKey || event.metaKey) return
      const actions: Record<string, () => void> = {
        ArrowLeft: back,
        ArrowRight: forward,
        Home: () => {
          if (exploration) setExploration({ ...exploration, index: 0 })
          else setPosition(0)
        },
        End: () => {
          if (exploration) setExploration({ ...exploration, index: exploration.moves.length })
          else setPosition(last)
        },
        Escape: () => {
          if (exploration) select(exploration.base)
        },
      }
      const action = Object.hasOwn(actions, event.key) ? actions[event.key] : undefined
      if (action) {
        event.preventDefault()
        action()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [back, forward, exploration, last, select])

  const onBoardMove = (uci: string) => {
    if (exploration) {
      const moves = [...exploration.moves.slice(0, exploration.index), uci]
      setExploration({ ...exploration, moves, index: moves.length })
    } else if (review.moves[position]?.uci === uci) {
      setPosition(position + 1) // the game move: just advance
    } else {
      setExploration({ base: position, moves: [uci], index: 1 })
    }
  }

  const onLine = (from: 'before' | 'after', sans: string[], index: number) => {
    const base = from === 'before' ? position - 1 : position
    const moves = sansToUcis(fens[base] ?? game.initial_fen, sans)
    setExploration({ base, moves, index: Math.min(index + 1, moves.length) })
  }

  const exploring = exploration !== null
  const baseFen = exploration ? (fens[exploration.base] ?? game.initial_fen) : null
  const shownMoves = exploration ? exploration.moves.slice(0, exploration.index) : []
  const fen =
    exploration && baseFen ? fenAfter(baseFen, shownMoves) : (fens[position] ?? game.initial_fen)
  const { evaluation, loading } = useEvaluation(
    exploration && baseFen ? { fen: baseFen, moves: shownMoves } : null,
  )

  const move = !exploring && position > 0 ? (review.moves[position - 1] ?? null) : null
  const meta = move ? CLASSIFICATIONS[move.classification] : null
  const arrows: BoardArrow[] = []
  let highlight: { from: string; to: string; color: string } | null = null
  if (move && meta) {
    highlight = { from: move.uci.slice(0, 2), to: move.uci.slice(2, 4), color: meta.color }
    arrows.push({ from: move.uci.slice(0, 2), to: move.uci.slice(2, 4), color: meta.color })
    if (move.best_uci && move.best_uci !== move.uci) {
      arrows.push({
        from: move.best_uci.slice(0, 2),
        to: move.best_uci.slice(2, 4),
        color: BEST_ARROW,
      })
    }
  }
  if (exploration) {
    const lastMove = shownMoves.at(-1)
    if (lastMove)
      highlight = { from: lastMove.slice(0, 2), to: lastMove.slice(2, 4), color: '#f0c419' }
    if (evaluation?.best_uci) {
      const b = evaluation.best_uci
      arrows.push({ from: b.slice(0, 2), to: b.slice(2, 4), color: BEST_ARROW })
    }
  }
  const badge =
    move && meta
      ? { square: move.uci.slice(2, 4), mark: meta.mark, color: meta.color, label: meta.label }
      : null
  const barEval = exploring ? (evaluation?.white ?? null) : (review.evals[position] ?? null)
  const names = playerNames(game)
  const start = fenStart(game.initial_fen)

  const navButton =
    'rounded border border-gray-300 px-3 py-1 text-lg hover:bg-gray-100 disabled:opacity-40'
  const panel = (id: Tab) => `${tab === id ? '' : 'hidden'} lg:block`

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,560px)_1fr]">
      <div className="flex min-w-0 flex-col gap-2">
        <EvalBar
          evaluation={barEval}
          orientation="horizontal"
          boardOrientation={orientation}
          className="lg:hidden"
        />
        <div className="flex gap-2">
          <EvalBar
            evaluation={barEval}
            orientation="vertical"
            boardOrientation={orientation}
            className="hidden lg:flex"
          />
          <div className="min-w-0 flex-1">
            <ReviewBoard
              fen={fen}
              orientation={orientation}
              arrows={arrows}
              highlight={highlight}
              badge={badge}
              onMove={onBoardMove}
            />
          </div>
        </div>
        <div className="flex items-center justify-center gap-2" aria-label="Navegación">
          <button
            type="button"
            className={navButton}
            aria-label="Principio"
            onClick={() => {
              select(0)
            }}
          >
            ⏮
          </button>
          <button type="button" className={navButton} aria-label="Anterior" onClick={back}>
            ◀
          </button>
          <button type="button" className={navButton} aria-label="Siguiente" onClick={forward}>
            ▶
          </button>
          <button
            type="button"
            className={navButton}
            aria-label="Final"
            onClick={() => {
              select(last)
            }}
          >
            ⏭
          </button>
        </div>
        {exploration && baseFen && (
          <div
            role="status"
            aria-label="Variante explorada"
            className="rounded border border-amber-300 bg-amber-50 p-2 text-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">
                Explorando una variante desde{' '}
                {exploration.base === 0
                  ? 'la posición inicial'
                  : `${moveNumber(exploration.base - 1)} ${review.moves[exploration.base - 1]?.san ?? ''}`}
              </span>
              <button
                type="button"
                className="ml-auto rounded bg-amber-600 px-2 py-0.5 text-white hover:bg-amber-700"
                onClick={() => {
                  select(exploration.base)
                }}
              >
                Volver a la partida
              </button>
            </div>
            <p className="mt-1 font-mono">
              {ucisToSans(baseFen, exploration.moves).map((san, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setExploration({ ...exploration, index: i + 1 })
                  }}
                  className={`mr-1 rounded px-1 ${i + 1 === exploration.index ? 'bg-amber-200 font-semibold' : 'hover:bg-amber-100'}`}
                >
                  {san}
                </button>
              ))}
            </p>
            <p className="mt-1 text-gray-700" aria-live="polite">
              {loading || !evaluation
                ? 'Evaluando…'
                : evaluation.terminal
                  ? { checkmate: 'Jaque mate.', stalemate: 'Ahogado: tablas.', draw: 'Tablas.' }[
                      evaluation.terminal
                    ]
                  : `Evaluación ${evalLabel(evaluation.white)} · mejor línea: ${
                      evaluation.lines.at(0)?.san.join(' ') ?? evaluation.best_san ?? '–'
                    }`}
            </p>
          </div>
        )}
        <EvalGraph
          evals={review.evals}
          moves={review.moves}
          keyMoments={review.key_moments}
          position={exploration ? exploration.base : position}
          onSelect={select}
        />
      </div>

      <div className="flex min-w-0 flex-col gap-4">
        <div role="tablist" aria-label="Secciones" className="flex gap-1 border-b lg:hidden">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => {
                setTab(t.id)
              }}
              className={`px-3 py-1.5 text-sm ${tab === t.id ? 'border-b-2 border-blue-700 font-semibold text-blue-800' : 'text-gray-600'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <section aria-label="Detalle de la jugada" className={panel('move')}>
          {exploring ? (
            <p className="text-sm text-gray-500">
              Estás explorando una variante. Vuelve a la partida para ver la clasificación.
            </p>
          ) : (
            <MoveDetail move={move} evalAfter={review.evals[position] ?? null} onLine={onLine} />
          )}
        </section>
        <section aria-label="Lista de jugadas" className={panel('moves')}>
          <MoveTable
            moves={review.moves}
            position={exploration ? exploration.base : position}
            onSelect={select}
            firstMoveNumber={start.moveNumber}
            blackStarts={start.blackToMove}
          />
        </section>
        <section aria-label="Resumen de la partida" className={panel('summary')}>
          <ReviewSummary
            review={review}
            whiteName={names.white}
            blackName={names.black}
            onSelect={select}
          />
        </section>
      </div>
    </div>
  )
}
