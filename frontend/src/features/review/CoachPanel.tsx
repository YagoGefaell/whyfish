import { BookOpen, ChevronDown, Lightbulb, ListTree, PlayCircle, Target } from 'lucide-react'
import { useState } from 'react'
import type { Explanation, MoveRef, MoveReview, WhiteEval } from '../../api/analysis'
import { ClassBadge } from '../../components/ClassBadge'
import { readFlag, writeFlag } from '../../lib/storage'
import { CLASSIFICATIONS, evalLabel, moveNumber, showsAlternative } from './classification'
import { MoveExplanation } from './MoveExplanation'
import { canTry as canTryMove, whyKindOf } from './why/kinds'

const DETAILS_KEY = 'whyfish.review.engineDetails'

interface Props {
  move: MoveReview | null
  evalAfter: WhiteEval | null
  /** Explore a line on the board: from the position before the move (best) or after it. */
  onLine: (from: 'before' | 'after', sans: string[], index: number) => void
  /** Explanation at the level shown (level 2 when `deep`). */
  explanation: Explanation | null
  explanationLoading: boolean
  deep: boolean
  onDeep: (deep: boolean) => void
  /** A move of the explanation was clicked: show it on the board. */
  onRef: (ref: MoveRef) => void
  /** "Ver por qué" (refutation) / "Ver la idea" (idea). */
  onWhy: (kind: 'refutation' | 'idea') => void
  /** "Pruébalo tú" on errors. */
  onTry: () => void
  /** The sequence is being prepared (the engine may extend it). */
  whyLoading: boolean
  whyError: string | null
}

/** SAN line with move numbers ("4… Nd7 5. exd6 Bxd6"); every move is clickable. */
function Line({
  sans,
  firstPly,
  onPick,
  label,
}: {
  sans: string[]
  firstPly: number
  onPick: (i: number) => void
  label: string
}) {
  return (
    <span className="tabular inline-flex flex-wrap items-center gap-x-1 gap-y-1" aria-label={label}>
      {sans.map((san, i) => {
        const ply = firstPly + i
        const number =
          ply % 2 === 0 ? `${String(ply / 2 + 1)}.` : i === 0 ? `${String((ply + 1) / 2)}…` : null
        return (
          <span key={i} className="inline-flex items-center gap-1">
            {number && <span className="text-sm text-muted">{number}</span>}
            <button
              type="button"
              onClick={() => {
                onPick(i)
              }}
              className="rounded-md bg-panel-2 px-1.5 py-0.5 text-sm font-medium hover:bg-[#45423e]"
            >
              {san}
            </button>
          </span>
        )
      })}
    </span>
  )
}

/** Clickable SAN moves joined with commas and "o" ("Nf3, d4 o c4"). */
function EqualMoves({ sans, onPick }: { sans: string[]; onPick: (san: string) => void }) {
  return (
    <>
      {sans.map((san, i) => (
        <span key={san}>
          {i > 0 && (i === sans.length - 1 ? ' o ' : ', ')}
          <button
            type="button"
            onClick={() => {
              onPick(san)
            }}
            className="tabular rounded-md bg-panel-2 px-1.5 py-px font-semibold hover:bg-[#45423e]"
          >
            {san}
          </button>
        </span>
      ))}
    </>
  )
}

/** "Coach" card for the selected move: verdict, explanation, actions, engine details. */
export function CoachPanel({
  move,
  evalAfter,
  onLine,
  explanation,
  explanationLoading,
  deep,
  onDeep,
  onRef,
  onWhy,
  onTry,
  whyLoading,
  whyError,
}: Props) {
  const [detailsOpen, setDetailsOpen] = useState(() => readFlag(DETAILS_KEY, false))
  const [lineOpen, setLineOpen] = useState(false)

  if (!move) {
    return (
      <div className="flex flex-col gap-2">
        <h3 className="text-lg font-semibold">Posición inicial</h3>
        <p className="text-muted">
          Avanza con → o pulsa «Siguiente error» para ir a lo importante.
        </p>
      </div>
    )
  }
  const meta = CLASSIFICATIONS[move.classification]
  const alternative = showsAlternative(move)
  const canDeepen = deep || Boolean(explanation?.text)
  const whyKind = whyKindOf(move, explanation)
  // A best move (★, !, !!): the other moves as good as it ("También valía Y").
  const isBest = ['best', 'great', 'brilliant'].includes(move.classification)
  const alsoGood = isBest
    ? [
        ...(move.best_san && move.best_uci !== move.uci ? [move.best_san] : []),
        ...move.equal_best_san.filter((_, i) => move.equal_best_uci[i] !== move.uci),
      ]
    : []
  const canTry = canTryMove(move)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <ClassBadge classification={move.classification} size={32} />
        <h3 className="text-lg font-semibold leading-tight">
          <span className="tabular">
            {moveNumber(move.ply)} {move.san}
          </span>{' '}
          <span style={{ color: meta.color }}>{meta.phrase}</span>
        </h3>
      </div>
      <MoveExplanation explanation={explanation} loading={explanationLoading} onRef={onRef} />

      {alternative && (
        <p
          aria-label="Mejor jugada"
          className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-panel-2/60 px-3 py-2 text-sm"
        >
          <ClassBadge classification="best" size={18} />
          La mejor era <strong className="tabular text-accent-strong">{move.best_san}</strong>
          {move.equal_best_san.length > 0 && (
            <span>
              (o{' '}
              <EqualMoves
                sans={move.equal_best_san}
                onPick={(san) => {
                  onLine('before', [san], 0)
                }}
              />
              , igual de buena)
            </span>
          )}
        </p>
      )}
      {!alternative && alsoGood.length > 0 && (
        <p className="text-sm" aria-label="Igual de buenas">
          También valía{' '}
          <EqualMoves
            sans={alsoGood}
            onPick={(san) => {
              onLine('before', [san], 0)
            }}
          />
          .
        </p>
      )}

      {/* Actions: "Ver por qué" / "Ver la idea", "Pruébalo tú", "Profundizar", "Ver línea". */}
      {(alternative || canDeepen || whyKind || canTry) && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Acciones">
          {whyKind && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={whyLoading}
              onClick={() => {
                onWhy(whyKind)
              }}
            >
              {whyKind === 'refutation' ? <PlayCircle size={16} /> : <Lightbulb size={16} />}
              {whyLoading
                ? 'Preparando…'
                : whyKind === 'refutation'
                  ? 'Ver por qué'
                  : 'Ver la idea'}
            </button>
          )}
          {canTry && (
            <button type="button" className="btn" onClick={onTry}>
              <Target size={16} /> Pruébalo tú
            </button>
          )}
          {canDeepen && (
            <button
              type="button"
              className="btn"
              aria-expanded={deep}
              onClick={() => {
                onDeep(!deep)
              }}
            >
              <BookOpen size={16} /> {deep ? 'Menos detalle' : 'Profundizar'}
            </button>
          )}
          {alternative && (
            <button
              type="button"
              className="btn"
              aria-expanded={lineOpen}
              onClick={() => {
                setLineOpen((open) => !open)
              }}
            >
              <ListTree size={16} /> {lineOpen ? 'Ocultar línea' : 'Ver línea'}
            </button>
          )}
        </div>
      )}
      {whyError && <p className="text-sm text-[#f87171]">{whyError}</p>}
      {alternative && lineOpen && (
        <Line
          label="Línea de la mejor jugada"
          firstPly={move.ply}
          sans={move.best_line}
          onPick={(i) => {
            onLine('before', move.best_line, i)
          }}
        />
      )}

      <details
        open={detailsOpen}
        onToggle={(e) => {
          const open = e.currentTarget.open
          setDetailsOpen(open)
          writeFlag(DETAILS_KEY, open)
        }}
        className="group rounded-lg border border-line"
      >
        <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-sm text-muted hover:text-fg">
          Detalles del motor
          <ChevronDown size={16} className="transition-transform group-open:rotate-180" />
        </summary>
        <dl className="tabular grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 px-3 pb-3 text-sm">
          <dt className="text-muted">
            Prob. de ganar ({move.color === 'white' ? 'blancas' : 'negras'})
          </dt>
          <dd>
            {move.win_before.toFixed(0)} % → {move.win_after.toFixed(0)} %
            {move.delta >= 0.5 && <span className="text-muted"> (−{move.delta.toFixed(1)})</span>}
          </dd>
          {evalAfter && (
            <>
              <dt className="text-muted">Evaluación (blancas)</dt>
              <dd>{evalLabel(evalAfter)}</dd>
            </>
          )}
          <dt className="text-muted">Precisión</dt>
          <dd>{move.accuracy.toFixed(0)} %</dd>
          {move.best_san && move.best_uci !== move.uci && (
            <>
              <dt className="text-muted">Mejor línea</dt>
              <dd>
                <Line
                  label="Línea del motor"
                  firstPly={move.ply}
                  sans={move.best_line}
                  onPick={(i) => {
                    onLine('before', move.best_line, i)
                  }}
                />
              </dd>
            </>
          )}
          {move.played_line.length > 0 && (
            <>
              <dt className="text-muted">Tras {move.san}</dt>
              <dd>
                <Line
                  label="Continuación tras la jugada"
                  firstPly={move.ply + 1}
                  sans={move.played_line}
                  onPick={(i) => {
                    onLine('after', move.played_line, i)
                  }}
                />
              </dd>
            </>
          )}
        </dl>
      </details>
    </div>
  )
}
