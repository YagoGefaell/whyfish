import { ArrowRight, Check, ExternalLink, Lightbulb, RotateCcw, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { analysisApi, type Why } from '../../api/analysis'
import { ApiError } from '../../api/client'
import {
  trainingApi,
  type Exercise as ExerciseData,
  type TrainingAttempt,
} from '../../api/training'
import { fenAfter } from '../review/variation'
import { ReviewBoard, type MarkedSquare } from '../review/ReviewBoard'
import { useWhyPlayer } from '../review/why/useWhyPlayer'
import { WhyBar, WhyPanel } from '../review/why/WhyViews'

type Stage =
  | { kind: 'solving' }
  | { kind: 'checking'; uci: string }
  | { kind: 'done'; uci: string; attempt: TrainingAttempt }
  | { kind: 'error'; message: string }

const squares = (uci: string) => ({ from: uci.slice(0, 2), to: uci.slice(2, 4) })

/** Text with [[SAN]] marks shown as bold moves (no board link here). */
function Marked({ text }: { text: string }) {
  const parts = text.split(/\[\[([^[\]]+)\]\]/g)
  return (
    <p>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="tabular">
            {part}
          </strong>
        ) : (
          part
        ),
      )}
    </p>
  )
}

interface Props {
  sessionId: number
  position: number
  itemId: number
  /** The session after an answer (progress, streak). */
  onAnswered: (attempt: TrainingAttempt) => void
  onNext: () => void
}

/** One exercise: context (never the solution), the board, the answer and its replays. */
export function Exercise({ sessionId, position, itemId, onAnswered, onNext }: Props) {
  const [exercise, setExercise] = useState<ExerciseData | null>(null)
  const [stage, setStage] = useState<Stage>({ kind: 'solving' })
  const [replay, setReplay] = useState<Why | null>(null)
  const [solved, setSolved] = useState(false) // right, or the solution was seen: links shown
  const [loadingWhy, setLoadingWhy] = useState(false)
  const player = useWhyPlayer(replay)

  useEffect(() => {
    trainingApi
      .exercise(itemId)
      .then(setExercise)
      .catch(() => {
        setStage({ kind: 'error', message: 'No se pudo cargar el ejercicio.' })
      })
  }, [itemId])

  if (stage.kind === 'error' && !exercise) return <p className="text-danger">{stage.message}</p>
  if (!exercise) return <p className="text-muted">Cargando ejercicio…</p>

  const done = stage.kind === 'done' ? stage.attempt : null
  const right = done?.result.correct ?? false
  const side = exercise.context.color === 'white' ? 'las blancas' : 'las negras'
  const pace = exercise.context.pace ? `, ${exercise.context.pace}` : ''

  const answer = (uci: string) => {
    if (stage.kind !== 'solving') return
    setStage({ kind: 'checking', uci })
    trainingApi
      .attempt(sessionId, position, uci)
      .then((attempt) => {
        setStage({ kind: 'done', uci, attempt })
        if (attempt.result.correct) setSolved(true)
        onAnswered(attempt)
      })
      .catch((err: unknown) => {
        setStage({
          kind: 'error',
          message: err instanceof ApiError ? err.message : 'No se pudo comprobar la jugada.',
        })
      })
  }
  const showSolution = (kind: 'solution') => {
    if (!done) return
    setLoadingWhy(true)
    analysisApi
      .why(done.game_id, done.ply, kind)
      .then((why) => {
        setReplay(why)
        setSolved(true)
      })
      .catch(() => {
        setStage({ kind: 'error', message: 'No se pudo preparar la solución.' })
      })
      .finally(() => {
        setLoadingWhy(false)
      })
  }

  // Board: the replay, or the exercise (with the attempt once made).
  let fen = exercise.fen
  let shownMove: { from: string; to: string; classification: null } | null = null
  let marks: MarkedSquare[] = []
  let arrows: { from: string; to: string; color: string }[] = []
  if (replay) {
    const step = player.index >= 0 ? replay.steps[player.index] : undefined
    fen = step?.fen ?? replay.start_fen
    shownMove = step ? { ...squares(step.uci), classification: null } : null
    marks = step?.consequence
      ? [{ square: step.uci.slice(2, 4), role: replay.tone === 'bad' ? 'danger' : 'good' }]
      : []
    arrows = (step?.arrows ?? []).map((a) => ({
      from: a.from_square,
      to: a.to_square,
      color: 'var(--color-arrow-threat)',
    }))
  } else if (stage.kind === 'checking' || stage.kind === 'done') {
    fen = fenAfter(exercise.fen, [stage.uci])
    shownMove = { ...squares(stage.uci), classification: null }
  } else if (exercise.kind === 'miss' && exercise.last_move) {
    // The opponent's error, highlighted.
    shownMove = { ...squares(exercise.last_move), classification: null }
  }

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-center">
      <div className="w-full min-w-0 lg:w-[min(calc(100vw-27rem),calc(100dvh-11rem))] lg:shrink-0">
        <p data-testid="to-move" className="mb-1.5 flex items-center gap-2 text-sm font-semibold">
          <span
            className={`inline-block h-3 w-3 rounded-full border border-line ${exercise.context.color === 'white' ? 'bg-white' : 'bg-black'}`}
            aria-hidden="true"
          />
          Juegan {side} (tú)
        </p>
        <ReviewBoard
          fen={fen}
          orientation={exercise.context.color}
          arrows={arrows}
          marks={marks}
          shownMove={shownMove}
          animate={replay !== null}
          interactive={!replay && stage.kind === 'solving'}
          onMove={answer}
        />
      </div>

      <section
        aria-label="Ejercicio"
        className="panel flex min-w-0 flex-col gap-3 p-4 lg:w-[380px]"
      >
        <p className="text-sm text-muted" data-testid="exercise-context">
          Partida contra {exercise.context.opponent} ({exercise.context.origin}
          {pace}), jugada {exercise.context.move_number}, juegas con {side.slice(4)}.
        </p>
        <h3 className="text-lg font-semibold">{exercise.prompt}</h3>

        {replay ? (
          <>
            <WhyPanel
              why={replay}
              player={player}
              onExit={() => {
                setReplay(null)
              }}
              onRef={() => undefined}
            />
            <WhyBar
              why={replay}
              player={player}
              onExit={() => {
                setReplay(null)
              }}
              onRef={() => undefined}
            />
          </>
        ) : (
          <>
            {stage.kind === 'solving' && <p className="text-sm">Haz tu jugada en el tablero.</p>}
            {stage.kind === 'checking' && <p className="text-muted">Comprobando…</p>}
            {stage.kind === 'error' && <p className="text-danger">{stage.message}</p>}
            {done && right && (
              <div role="status" aria-label="Resultado" className="flex flex-col gap-2">
                <p className="flex items-center gap-2 font-medium text-good">
                  <Check size={18} /> ¡Bien visto!
                  {done.result.also.length > 0 && (
                    <span className="text-fg">También valía {done.result.also.join(' o ')}.</span>
                  )}
                </p>
                {done.explanation?.text && <Marked text={done.explanation.text} />}
                {done.learned && <p className="text-sm text-muted">Ejercicio aprendido.</p>}
              </div>
            )}
            {done && !right && (
              <p role="status" aria-label="Resultado">
                <span className="tabular font-semibold">{done.result.san}</span> no es la mejor
                jugada.
              </p>
            )}
            {done && (
              <div className="flex flex-wrap gap-2" role="group" aria-label="Opciones">
                {right ? (
                  <button
                    type="button"
                    className="btn"
                    disabled={loadingWhy}
                    onClick={() => {
                      showSolution('solution')
                    }}
                  >
                    <Lightbulb size={14} /> Ver la idea
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        setStage({ kind: 'solving' })
                      }}
                    >
                      <RotateCcw size={14} /> Intentar otra vez
                    </button>
                    {done.result.why && (
                      <button
                        type="button"
                        className="btn"
                        onClick={() => {
                          setReplay(done.result.why)
                        }}
                      >
                        <Search size={14} /> Ver por qué falla tu intento
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn"
                      disabled={loadingWhy}
                      onClick={() => {
                        showSolution('solution')
                      }}
                    >
                      <Lightbulb size={14} /> {loadingWhy ? 'Preparando…' : 'Ver la solución'}
                    </button>
                  </>
                )}
                <button type="button" className="btn-primary" onClick={onNext}>
                  Siguiente <ArrowRight size={14} />
                </button>
              </div>
            )}
            {done && solved && (
              <p className="flex flex-wrap gap-3 text-sm">
                <Link
                  className="text-accent-strong hover:underline"
                  to={`/review/${String(done.game_id)}?ply=${String(done.ply)}`}
                >
                  Ver la partida
                </Link>
                {done.external_url && (
                  <a
                    className="inline-flex items-center gap-1 text-muted hover:text-fg"
                    href={done.external_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={14} /> Partida original
                  </a>
                )}
              </p>
            )}
          </>
        )}
      </section>
    </div>
  )
}
