import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw, X } from 'lucide-react'
import type { MoveRef, Why } from '../../../api/analysis'
import { MarkedParagraph } from '../MoveExplanation'
import type { WhyPlayer } from './useWhyPlayer'

const TONE = {
  bad: { text: 'text-bad', bg: 'bg-bad-strong/20', ring: 'ring-bad-strong/60' },
  good: { text: 'text-good', bg: 'bg-good-strong/20', ring: 'ring-good-strong/60' },
} as const

/** Caption of the current step (or of the start position), coloured on the consequence. */
export function WhyCaption({
  why,
  player,
  large = false,
}: {
  why: Why
  player: WhyPlayer
  large?: boolean
}) {
  const step = player.index >= 0 ? why.steps[player.index] : undefined
  const text = step
    ? step.caption
    : why.alternative
      ? `¿Y si en lugar de esa jugada se juega ${why.alternative}?`
      : 'Posición antes de la jugada.'
  return (
    <p
      aria-live="polite"
      aria-label="Paso actual"
      className={`${large ? 'text-lg' : 'line-clamp-2 min-h-[2.75rem] text-[15px]'} leading-snug font-medium ${
        step?.consequence ? TONE[why.tone].text : ''
      }`}
    >
      {step && <span className="tabular mr-2 text-muted">{step.label}</span>}
      {text}
    </p>
  )
}

/** ◀ ⏯ ▶, step counter and "Volver a la partida". */
export function WhyControls({
  why,
  player,
  onExit,
}: {
  why: Why
  player: WhyPlayer
  onExit: () => void
}) {
  const total = why.steps.length
  const atLast = player.index >= total - 1
  return (
    <div className="flex items-center gap-1.5" role="group" aria-label="Reproducción">
      <button
        type="button"
        className="btn px-2"
        aria-label="Paso anterior"
        disabled={player.index < 0}
        onClick={player.prev}
      >
        <ChevronLeft size={18} />
      </button>
      <button
        type="button"
        className="btn px-2"
        aria-label={atLast ? 'Repetir' : player.playing ? 'Pausa' : 'Reproducir'}
        onClick={player.toggle}
      >
        {atLast ? (
          <RotateCcw size={18} />
        ) : player.playing ? (
          <Pause size={18} />
        ) : (
          <Play size={18} />
        )}
      </button>
      <button
        type="button"
        className="btn px-2"
        aria-label="Paso siguiente"
        disabled={atLast}
        onClick={player.next}
      >
        <ChevronRight size={18} />
      </button>
      <span className="tabular px-1 text-sm text-muted" aria-label="Progreso">
        {Math.max(0, player.index + 1)}/{total}
      </span>
      <button type="button" className="btn ml-auto" onClick={onExit}>
        <X size={14} /> Volver a la partida
      </button>
    </div>
  )
}

/** End of the sequence: the result, "Repetir" and "Volver a la partida". */
export function WhyCard({
  why,
  onRepeat,
  onExit,
  onRef,
}: {
  why: Why
  onRepeat: () => void
  onExit: () => void
  onRef: (ref: MoveRef) => void
}) {
  return (
    <div
      role="status"
      aria-label="Resultado"
      className={`flex flex-col gap-2 rounded-lg p-3 ring-1 ${TONE[why.tone].bg} ${TONE[why.tone].ring}`}
    >
      <span className={`text-sm font-semibold ${TONE[why.tone].text}`}>Resultado</span>
      <div className="text-[15px] leading-relaxed">
        <MarkedParagraph text={why.summary} refs={why.refs} offset={0} onRef={onRef} />
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn" onClick={onRepeat}>
          <RotateCcw size={14} /> Repetir
        </button>
        <button type="button" className="btn" onClick={onExit}>
          <X size={14} /> Volver a la partida
        </button>
      </div>
    </div>
  )
}

/** Numbered sequence ("21… dxc3 22. Rxd8 …"); the engine's defence moves look different. */
export function WhySequence({ why, player }: { why: Why; player: WhyPlayer }) {
  return (
    <ol aria-label="Secuencia" className="tabular flex flex-wrap items-center gap-x-1 gap-y-1.5">
      {why.steps.map((step) => {
        const current = step.index === player.index
        const number = step.label.slice(0, step.label.length - step.san.length)
        const showNumber = step.color === 'white' || step.index === 0
        return (
          <li key={step.index} className="inline-flex items-center gap-1">
            {showNumber && <span className="text-sm text-muted">{number}</span>}
            <button
              type="button"
              onClick={() => {
                player.goTo(step.index)
              }}
              title={step.defense ? 'Tu mejor defensa según el motor' : undefined}
              aria-current={current ? 'step' : undefined}
              data-defense={step.defense || undefined}
              data-consequence={step.consequence || undefined}
              className={[
                'rounded-md px-1.5 py-0.5 text-sm font-medium',
                step.defense ? 'border border-dashed border-muted/60 italic' : '',
                step.consequence ? `${TONE[why.tone].bg} ${TONE[why.tone].text}` : '',
                current ? 'ring-2 ring-accent' : 'hover:bg-white/10',
              ].join(' ')}
            >
              {step.san}
            </button>
          </li>
        )
      })}
    </ol>
  )
}

/**
 * Bar in the navigation slot (just under the board on mobile, at the bottom of the panel on
 * desktop): on mobile the caption (or the final card) above the controls.
 */
export function WhyBar({
  why,
  player,
  onExit,
  onRef,
}: {
  why: Why
  player: WhyPlayer
  onExit: () => void
  onRef: (ref: MoveRef) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="lg:hidden">
        {player.atEnd ? (
          <WhyCard why={why} onRepeat={player.restart} onExit={onExit} onRef={onRef} />
        ) : (
          <WhyCaption why={why} player={player} />
        )}
      </div>
      <WhyControls why={why} player={player} onExit={onExit} />
    </div>
  )
}

/** Panel content while replaying: title, (desktop) caption or final card, sequence. */
export function WhyPanel({
  why,
  player,
  onExit,
  onRef,
}: {
  why: Why
  player: WhyPlayer
  onExit: () => void
  onRef: (ref: MoveRef) => void
}) {
  return (
    <section aria-label="Ver por qué" className="flex flex-col gap-3">
      <h3 className="text-lg leading-tight font-semibold">{why.title}</h3>
      <div className="hidden lg:block">
        {player.atEnd ? (
          <WhyCard why={why} onRepeat={player.restart} onExit={onExit} onRef={onRef} />
        ) : (
          <WhyCaption why={why} player={player} large />
        )}
      </div>
      <WhySequence why={why} player={player} />
    </section>
  )
}
