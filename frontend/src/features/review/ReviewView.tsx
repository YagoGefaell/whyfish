import { X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  analysisApi,
  type MoveRef,
  type MoveReview,
  type Review,
  type Why,
  type WhyKind,
} from '../../api/analysis'
import { ApiError } from '../../api/client'
import type { Color, GameState } from '../../api/games'
import { CoachPanel } from './CoachPanel'
import { CLASSIFICATIONS, evalLabel, moveNumber, showsAlternative } from './classification'
import { EvalBar } from './EvalBar'
import { EvalGraph } from './EvalGraph'
import { MoveList, type ListMove } from './MoveList'
import { playerNames } from './names'
import { NavBar } from './NavBar'
import { ReviewBoard, type BoardArrow, type MarkedSquare, type ShownMove } from './ReviewBoard'
import { ColorDot, SummaryPanel } from './SummaryPanel'
import { useEvaluation } from './useEvaluation'
import { useExplanation } from './useExplanation'
import { fenAfter, fenStart, mainLineFens, sansToUcis, ucisToSans } from './variation'
import { TryIt, type TryState } from './why/TryIt'
import { useWhyPlayer } from './why/useWhyPlayer'
import { WhyBar, WhyPanel } from './why/WhyViews'

// Intense green; react-chessboard applies the 0.8 opacity (ReviewBoard ARROW_OPTIONS).
const BEST_ARROW = '#16a34a'
/** Explanation arrows: the opponent's threat (red), what a good move attacks (amber). */
const ANNOTATION_ARROW = { threat: '#dc2626', attack: '#f59e0b' } as const
/** Threats drawn while replaying a sequence ("Ver por qué"). */
const WHY_ARROW = '#dc2626'

interface Exploration {
  base: number // main-line position the variation starts from
  moves: string[] // UCI
  index: number // how many of `moves` are shown (0 = the base position)
}

type Tab = 'summary' | 'review'

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

const squares = (uci: string) => ({ from: uci.slice(0, 2), to: uci.slice(2, 4) })

interface Props {
  game: GameState
  /** null while the game is being analysed (or was never analysed). */
  review: Review | null
  /** Shown in the panel instead of the review while there is none (progress, errors...). */
  status?: ReactNode
  /** Game info line (event · date · result · opening), aligned with the board. */
  meta?: ReactNode
  /** Open on this move (0-based ply), in the review tab: links from the statistics. */
  initialPly?: number | null
}

export function ReviewView({ game, review, status, meta, initialPly = null }: Props) {
  const moves = useMemo(() => game.moves.map((m) => m.uci), [game.moves])
  const fens = useMemo(() => mainLineFens(game.initial_fen, moves), [game.initial_fen, moves])
  const last = fens.length - 1
  const orientation = review?.perspective ?? game.player_color
  const opening = initialPly !== null && initialPly >= 0 && initialPly < game.moves.length
  // Position after move `initialPly` (position i = after i moves).
  const [position, setPosition] = useState(opening ? initialPly + 1 : 0)
  const [animate, setAnimate] = useState(false)
  const [exploration, setExploration] = useState<Exploration | null>(null)
  const [tab, setTab] = useState<Tab>(opening ? 'review' : 'summary')
  // "Profundizar" is open for this position only (closes when moving on).
  const [deepAt, setDeepAt] = useState<number | null>(null)
  // "Ver por qué": the sequence being replayed (fromTry: opened from "Pruébalo tú").
  const [why, setWhy] = useState<{ data: Why; fromTry: boolean } | null>(null)
  const player = useWhyPlayer(why?.data ?? null)
  const [whyLoading, setWhyLoading] = useState(false)
  const [whyError, setWhyError] = useState<{ ply: number; message: string } | null>(null)
  // "Pruébalo tú": the position before move `ply`.
  const [trying, setTrying] = useState<{ ply: number; state: TryState } | null>(null)

  /** Long jump: no animation, leaves any variation or replay, goes to the review tab. */
  const jump = useCallback((p: number) => {
    setAnimate(false)
    setExploration(null)
    setWhy(null)
    setTrying(null)
    setPosition(p)
    setTab('review')
  }, [])

  const openWhy = useCallback(
    (ply: number, kind: WhyKind, fromTry = false) => {
      setWhyLoading(true)
      setWhyError(null)
      analysisApi
        .why(game.id, ply, kind)
        .then((data) => {
          setExploration(null)
          setTab('review')
          setWhy({ data, fromTry })
        })
        .catch((error: unknown) => {
          const message =
            error instanceof ApiError ? error.message : 'No se ha podido preparar la secuencia.'
          setWhyError({ ply, message })
        })
        .finally(() => {
          setWhyLoading(false)
        })
    },
    [game.id],
  )
  const exitWhy = useCallback(() => {
    setAnimate(false)
    setWhy(null)
  }, [])
  const exitTry = useCallback(() => {
    setAnimate(false)
    setWhy(null)
    setTrying(null)
  }, [])

  const step = useCallback(
    (delta: 1 | -1) => {
      setAnimate(true)
      setTab('review')
      if (exploration) {
        const index = exploration.index + delta
        if (index < 0) {
          setExploration(null)
          setPosition(exploration.base)
        } else {
          setExploration({ ...exploration, index: Math.min(exploration.moves.length, index) })
        }
      } else {
        setPosition((p) => Math.min(last, Math.max(0, p + delta)))
      }
    },
    [exploration, last],
  )

  const nextError = useMemo(() => {
    if (!review) return null
    const from = exploration ? exploration.base : position
    const target = review.moves.find(
      (m) =>
        m.ply >= from &&
        m.color === review.perspective &&
        CLASSIFICATIONS[m.classification].isError,
    )
    return target ? target.ply + 1 : null
  }, [review, exploration, position])

  const goNextError = useMemo(
    () =>
      nextError === null
        ? null
        : () => {
            jump(nextError)
          },
    [nextError, jump],
  )

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.altKey || event.ctrlKey || event.metaKey) return
      if (why) {
        const replay: Partial<Record<string, () => void>> = {
          ArrowLeft: player.prev,
          ArrowRight: player.next,
          ' ': player.toggle,
          Escape: exitWhy,
        }
        const action = Object.hasOwn(replay, event.key) ? replay[event.key] : undefined
        if (action) {
          event.preventDefault()
          action()
        }
        return
      }
      if (trying && event.key === 'Escape') {
        event.preventDefault()
        exitTry()
        return
      }
      const actions: Record<string, (() => void) | null> = {
        ArrowLeft: () => {
          step(-1)
        },
        ArrowRight: () => {
          step(1)
        },
        Home: () => {
          jump(0)
        },
        End: () => {
          jump(last)
        },
        n: goNextError,
        N: goNextError,
        Escape: exploration
          ? () => {
              jump(exploration.base)
            }
          : null,
      }
      const action = Object.hasOwn(actions, event.key) ? actions[event.key] : null
      if (action) {
        event.preventDefault()
        action()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [step, jump, last, goNextError, exploration, why, player, exitWhy, trying, exitTry])

  const onBoardMove = (uci: string) => {
    setAnimate(false) // the piece was already dragged
    if (trying) {
      if (trying.state.status !== 'waiting') return
      const ply = trying.ply
      setTrying({ ply, state: { status: 'checking', uci } })
      analysisApi
        .tryMove(game.id, ply, uci)
        .then((result) => {
          setTrying((t) => (t?.ply === ply ? { ply, state: { status: 'done', result } } : t))
        })
        .catch((error: unknown) => {
          const message =
            error instanceof ApiError ? error.message : 'No se ha podido comprobar la jugada.'
          setTrying((t) => (t?.ply === ply ? { ply, state: { status: 'error', message } } : t))
        })
      return
    }
    if (exploration) {
      const next = [...exploration.moves.slice(0, exploration.index), uci]
      setExploration({ ...exploration, moves: next, index: next.length })
    } else if (moves[position] === uci) {
      setPosition(position + 1)
    } else {
      setExploration({ base: position, moves: [uci], index: 1 })
    }
  }

  const onLine = (from: 'before' | 'after', sans: string[], index: number) => {
    const base = from === 'before' ? position - 1 : position
    const line = sansToUcis(fens[base] ?? game.initial_fen, sans)
    setAnimate(false)
    setExploration({ base, moves: line, index: Math.min(index + 1, line.length) })
  }

  // The summary tab shows the final position of the game.
  const onSummary = review !== null && tab === 'summary' && !exploration
  const shownPosition = onSummary ? last : position
  const baseFen = exploration ? (fens[exploration.base] ?? game.initial_fen) : null
  const shownMoves = exploration ? exploration.moves.slice(0, exploration.index) : []
  const fen =
    exploration && baseFen
      ? fenAfter(baseFen, shownMoves)
      : (fens[shownPosition] ?? game.initial_fen)
  const { evaluation, loading } = useEvaluation(
    exploration && baseFen ? { fen: baseFen, moves: shownMoves } : null,
  )

  const reviewed: MoveReview | null =
    !exploration && review && shownPosition > 0 ? (review.moves[shownPosition - 1] ?? null) : null
  const deep = deepAt === position && reviewed !== null
  const explainedPly = review && tab === 'review' && reviewed ? reviewed.ply : null
  const level1 = useExplanation(game.id, explainedPly, 1)
  const level2 = useExplanation(game.id, deep ? explainedPly : null, 2)
  const explanation = deep && level2.explanation ? level2 : level1

  const onRef = (ref: MoveRef) => {
    setAnimate(false)
    const mainLine = moves.slice(ref.base, ref.base + ref.path.length)
    if (ref.path.every((uci, i) => mainLine[i] === uci)) {
      setExploration(null)
      setPosition(ref.base + ref.path.length)
    } else {
      setExploration({ base: ref.base, moves: ref.path, index: ref.path.length })
    }
  }

  const arrows: BoardArrow[] = []
  const marks: MarkedSquare[] = []
  let shownMove: ShownMove | null = null
  if (exploration) {
    const lastUci = shownMoves.at(-1)
    if (lastUci) shownMove = { ...squares(lastUci), classification: null }
    if (evaluation?.best_uci) arrows.push({ ...squares(evaluation.best_uci), color: BEST_ARROW })
  } else if (shownPosition > 0) {
    const uci = moves[shownPosition - 1]
    if (uci) shownMove = { ...squares(uci), classification: reviewed?.classification ?? null }
    if (reviewed?.best_uci && showsAlternative(reviewed)) {
      arrows.push({ ...squares(reviewed.best_uci), color: BEST_ARROW })
    }
    // What the explanation talks about, drawn on the position after the move.
    if (tab === 'review' && explanation.explanation?.ply === reviewed?.ply) {
      for (const a of explanation.explanation?.annotations ?? []) {
        if (a.kind === 'arrow' && a.from_square && a.to_square) {
          if (a.role === 'threat' || a.role === 'attack') {
            arrows.push({ from: a.from_square, to: a.to_square, color: ANNOTATION_ARROW[a.role] })
          }
        } else if (a.square && (a.role === 'danger' || a.role === 'target')) {
          marks.push({ square: a.square, role: a.role })
        }
      }
    }
  }
  // Replaying a sequence or trying a move: the board shows that instead.
  let boardFen = fen
  let boardArrows = arrows
  let boardMarks = marks
  let boardMove = shownMove
  let boardAnimate = animate
  let interactive = true
  let animationMs = 200
  if (why) {
    const data = why.data
    const current = player.index >= 0 ? data.steps[player.index] : undefined
    boardFen = current?.fen ?? data.start_fen
    boardArrows = (current?.arrows ?? []).map((a) => ({
      from: a.from_square,
      to: a.to_square,
      color: WHY_ARROW,
    }))
    boardMove = current ? { ...squares(current.uci), classification: null } : null
    boardMarks = current?.consequence
      ? [{ square: current.uci.slice(2, 4), role: data.tone === 'bad' ? 'danger' : 'good' }]
      : []
    boardAnimate = true
    interactive = false
    animationMs = Math.min(450, Math.round(data.step_ms * 0.45))
  } else if (trying) {
    const before = fens[trying.ply] ?? game.initial_fen
    const attempt =
      trying.state.status === 'checking'
        ? trying.state.uci
        : trying.state.status === 'done'
          ? trying.state.result.uci
          : null
    boardFen = attempt ? fenAfter(before, [attempt]) : before
    boardArrows = [] // the best move must not be given away
    boardMarks = []
    boardMove = attempt ? { ...squares(attempt), classification: null } : null
    interactive = trying.state.status === 'waiting'
  }
  const barEval = exploration ? (evaluation?.white ?? null) : (review?.evals[shownPosition] ?? null)
  const names = playerNames(game)
  const start = fenStart(game.initial_fen)
  const listMoves: ListMove[] = game.moves.map((m) => ({
    ply: m.ply,
    san: m.san,
    classification: review?.moves[m.ply]?.classification ?? null,
  }))

  const nav = (
    <NavBar
      onFirst={() => {
        jump(0)
      }}
      onBack={() => {
        step(-1)
      }}
      onForward={() => {
        step(1)
      }}
      onLast={() => {
        jump(last)
      }}
      onNextError={review ? goNextError : null}
    />
  )

  const accuracyOf = (color: Color) => review?.[color].accuracy ?? null
  const topColor: Color = orientation === 'white' ? 'black' : 'white'

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:justify-center">
      {/*
        Board column: game info line, player strips, eval bar (2.25rem) + board. On desktop the
        board takes the whole available height (the width follows it); the graph is in the panel.
      */}
      <div className="flex w-full min-w-0 flex-col gap-1.5 lg:w-[min(calc(100vw-26.75rem),calc(100dvh-7.25rem))] lg:shrink-0">
        {meta && <div className="truncate text-sm text-muted lg:ml-9">{meta}</div>}
        <EvalBar
          evaluation={barEval}
          orientation="horizontal"
          boardOrientation={orientation}
          className="my-1 lg:hidden"
        />
        <PlayerStrip
          name={names[topColor]}
          color={topColor}
          isUser={false}
          accuracy={accuracyOf(topColor)}
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
              fen={boardFen}
              orientation={orientation}
              arrows={boardArrows}
              marks={boardMarks}
              shownMove={boardMove}
              animate={boardAnimate}
              onMove={onBoardMove}
              interactive={interactive}
              animationMs={animationMs}
            />
          </div>
        </div>
        <PlayerStrip
          name={names[orientation]}
          color={orientation}
          isUser
          accuracy={accuracyOf(orientation)}
        />
      </div>

      {/* Panel: same height as the board column on desktop; graph on top, nav at the bottom. */}
      <div className="relative min-w-0 lg:w-[380px] lg:shrink-0 xl:w-[400px]">
        <section
          aria-label="Panel de revisión"
          className="panel flex flex-col lg:absolute lg:inset-0"
        >
          <div className="order-first border-b border-line p-3 lg:order-last lg:border-t lg:border-b-0">
            {why ? (
              <WhyBar
                why={why.data}
                player={player}
                onExit={exitWhy}
                onRef={(ref) => {
                  exitTry()
                  onRef(ref)
                }}
              />
            ) : (
              nav
            )}
          </div>
          <div className={`p-3 pb-0 ${why || trying ? 'opacity-50' : ''}`}>
            {review ? (
              <EvalGraph
                evals={review.evals}
                moves={review.moves}
                position={exploration ? exploration.base : shownPosition}
                onSelect={jump}
                className="h-20 lg:h-24"
              />
            ) : (
              <div className="h-20 rounded-lg bg-panel-2 lg:h-24" aria-hidden="true" />
            )}
          </div>
          {review ? (
            <div role="tablist" aria-label="Secciones" className="flex border-b border-line px-2">
              {(
                [
                  ['summary', 'Resumen'],
                  ['review', 'Revisión'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => {
                    setTab(id)
                  }}
                  className={`flex-1 border-b-2 px-3 py-2.5 text-sm font-semibold ${
                    tab === id
                      ? 'border-accent text-fg'
                      : 'border-transparent text-muted hover:text-fg'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
          <div
            className={`flex min-h-0 flex-1 flex-col gap-4 p-4 ${
              review && tab === 'summary' ? 'overflow-y-auto' : 'lg:overflow-hidden'
            }`}
          >
            {!review && status}
            {review && tab === 'summary' && (
              <SummaryPanel
                review={review}
                names={names}
                onStart={() => {
                  jump(1)
                }}
                onSelect={jump}
              />
            )}
            {review && tab === 'review' && (
              <div className="shrink-0 lg:max-h-[68%] lg:overflow-y-auto">
                {why ? (
                  <WhyPanel
                    why={why.data}
                    player={player}
                    onExit={exitWhy}
                    onRef={(ref) => {
                      exitTry()
                      onRef(ref)
                    }}
                  />
                ) : trying ? (
                  <TryIt
                    state={trying.state}
                    side={review.moves[trying.ply]?.color ?? 'white'}
                    busy={whyLoading}
                    onRetry={() => {
                      setTrying({ ply: trying.ply, state: { status: 'waiting' } })
                    }}
                    onWhyAttempt={() => {
                      if (trying.state.status === 'done' && trying.state.result.why) {
                        setWhy({ data: trying.state.result.why, fromTry: true })
                      }
                    }}
                    onSolution={() => {
                      openWhy(trying.ply, 'solution', true)
                    }}
                    onExit={exitTry}
                  />
                ) : exploration && baseFen ? (
                  <ExplorationCard
                    base={
                      exploration.base === 0
                        ? 'la posición inicial'
                        : `${moveNumber(exploration.base - 1)} ${game.moves[exploration.base - 1]?.san ?? ''}`
                    }
                    sans={ucisToSans(baseFen, exploration.moves)}
                    index={exploration.index}
                    onPick={(i) => {
                      setAnimate(false)
                      setExploration({ ...exploration, index: i + 1 })
                    }}
                    onExit={() => {
                      jump(exploration.base)
                    }}
                    text={
                      loading || !evaluation
                        ? 'Evaluando…'
                        : evaluation.terminal
                          ? {
                              checkmate: 'Jaque mate.',
                              stalemate: 'Ahogado: tablas.',
                              draw: 'Tablas.',
                            }[evaluation.terminal]
                          : `Evaluación ${evalLabel(evaluation.white)} · mejor línea: ${evaluation.lines.at(0)?.san.join(' ') ?? evaluation.best_san ?? '–'}`
                    }
                  />
                ) : (
                  <CoachPanel
                    key={position}
                    move={reviewed}
                    evalAfter={review.evals[position] ?? null}
                    onLine={onLine}
                    explanation={explanation.explanation}
                    explanationLoading={explanation.loading}
                    deep={deep}
                    onDeep={(open) => {
                      setDeepAt(open ? position : null)
                    }}
                    onRef={onRef}
                    onWhy={(kind) => {
                      if (reviewed) openWhy(reviewed.ply, kind)
                    }}
                    onTry={() => {
                      if (!reviewed) return
                      setExploration(null)
                      setAnimate(false)
                      setTrying({ ply: reviewed.ply, state: { status: 'waiting' } })
                    }}
                    whyLoading={whyLoading}
                    whyError={whyError?.ply === reviewed?.ply ? (whyError?.message ?? null) : null}
                  />
                )}
              </div>
            )}
            {(!review || tab === 'review') && (
              <div
                className={`flex min-h-0 flex-1 flex-col border-t border-line pt-3 ${
                  why || trying ? 'opacity-50' : ''
                }`}
              >
                <MoveList
                  moves={listMoves}
                  position={exploration ? exploration.base : position}
                  onSelect={jump}
                  firstMoveNumber={start.moveNumber}
                  blackStarts={start.blackToMove}
                />
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

/** Player name with a colour dot; the user is always at the bottom. */
function PlayerStrip({
  name,
  color,
  isUser,
  accuracy,
}: {
  name: string
  color: Color
  isUser: boolean
  accuracy: number | null
}) {
  return (
    <div
      data-testid={isUser ? 'player-bottom' : 'player-top'}
      className="flex h-6 items-center gap-2 text-sm font-semibold lg:ml-9"
    >
      <ColorDot color={color} />
      <span className="truncate">{name}</span>
      {isUser && name !== 'Tú' && (
        <span className="rounded bg-panel-2 px-1.5 text-xs font-medium text-muted">tú</span>
      )}
      {accuracy !== null && (
        <span
          className="tabular ml-auto rounded-md bg-panel-2 px-2 text-xs font-semibold"
          title="Precisión"
          data-testid={isUser ? 'player-bottom-accuracy' : 'player-top-accuracy'}
        >
          {accuracy.toFixed(1)}
          <span className="sr-only"> de precisión</span>
        </span>
      )}
    </div>
  )
}

function ExplorationCard(props: {
  base: string
  sans: string[]
  index: number
  text: string
  onPick: (i: number) => void
  onExit: () => void
}) {
  return (
    <div
      role="status"
      aria-label="Variante explorada"
      className="flex flex-col gap-2 rounded-lg border border-[#f7c631]/40 bg-[#f7c631]/10 p-3 text-sm"
    >
      <div className="flex items-center gap-2">
        <span className="font-semibold">Variante desde {props.base}</span>
        <button type="button" className="btn ml-auto" onClick={props.onExit}>
          <X size={14} /> Volver a la partida
        </button>
      </div>
      <p className="tabular flex flex-wrap gap-1">
        {props.sans.map((san, i) => (
          <button
            key={i}
            type="button"
            onClick={() => {
              props.onPick(i)
            }}
            className={`rounded-md px-1.5 py-0.5 font-medium ${i + 1 === props.index ? 'bg-[#f7c631]/30' : 'hover:bg-white/10'}`}
          >
            {san}
          </button>
        ))}
      </p>
      <p className="text-muted" aria-live="polite">
        {props.text}
      </p>
    </div>
  )
}
