import { Check, Lightbulb, RotateCcw, Search, X } from 'lucide-react'
import type { TryResult } from '../../../api/analysis'
import type { Color } from '../../../api/games'
import { CLASSIFICATIONS } from '../classification'

export type TryState =
  | { status: 'waiting' }
  | { status: 'checking'; uci: string }
  | { status: 'done'; result: TryResult }
  | { status: 'error'; message: string }

interface Props {
  state: TryState
  side: Color
  /** Loading the explanation of the attempt or the solution. */
  busy: boolean
  onRetry: () => void
  onWhyAttempt: () => void
  onSolution: () => void
  onExit: () => void
}

/** "Pruébalo tú": find the best move in the position before the user's move. */
export function TryIt({ state, side, busy, onRetry, onWhyAttempt, onSolution, onExit }: Props) {
  const who = side === 'white' ? 'las blancas' : 'las negras'
  return (
    <section
      aria-label="Pruébalo tú"
      className="flex flex-col gap-3 rounded-lg border border-accent/40 bg-accent/10 p-3"
    >
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">Pruébalo tú</h3>
        <button type="button" className="btn ml-auto" onClick={onExit}>
          <X size={14} /> Volver a la partida
        </button>
      </div>
      {state.status === 'waiting' && <p>Busca la mejor jugada para {who} y hazla en el tablero.</p>}
      {state.status === 'checking' && <p className="text-muted">Comprobando tu jugada…</p>}
      {state.status === 'error' && <p className="text-[#f87171]">{state.message}</p>}
      {state.status === 'done' && state.result.correct && (
        <p className="flex items-center gap-2 font-medium text-[#4ade80]">
          <Check size={18} /> ¡Bien visto! <span className="tabular">{state.result.san}</span> es la
          mejor jugada.
        </p>
      )}
      {state.status === 'done' && !state.result.correct && (
        <>
          <p>
            <span className="tabular font-semibold">{state.result.san}</span>{' '}
            <span style={{ color: CLASSIFICATIONS[state.result.classification].color }}>
              {CLASSIFICATIONS[state.result.classification].phrase}
            </span>
            : no es la mejor.
          </p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Opciones">
            <button type="button" className="btn" onClick={onRetry}>
              <RotateCcw size={14} /> Intentar otra vez
            </button>
            {state.result.why && (
              <button type="button" className="btn" disabled={busy} onClick={onWhyAttempt}>
                <Search size={14} /> Ver por qué falla tu intento
              </button>
            )}
            <button type="button" className="btn" disabled={busy} onClick={onSolution}>
              <Lightbulb size={14} /> {busy ? 'Preparando…' : 'Ver la solución'}
            </button>
          </div>
        </>
      )}
    </section>
  )
}
