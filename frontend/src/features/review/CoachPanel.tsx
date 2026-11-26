import { BookOpen, ChevronDown, ListTree } from 'lucide-react'
import { useState } from 'react'
import type { Explanation, MoveRef, MoveReview, WhiteEval } from '../../api/analysis'
import { ClassBadge } from '../../components/ClassBadge'
import { readFlag, writeFlag } from '../../lib/storage'
import { CLASSIFICATIONS, evalLabel, moveNumber, showsAlternative } from './classification'
import { MoveExplanation } from './MoveExplanation'

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
        <p className="flex items-center gap-2 rounded-lg bg-panel-2/60 px-3 py-2 text-sm">
          <ClassBadge classification="best" size={18} />
          La mejor era <strong className="tabular text-accent-strong">{move.best_san}</strong>
        </p>
      )}

      {/* Actions: "Profundizar" (level 2), "Ver línea"; "Pruébalo tú" comes in phase 6. */}
      {(alternative || canDeepen) && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Acciones">
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
