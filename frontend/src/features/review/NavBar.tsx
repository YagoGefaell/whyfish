import {
  ChevronFirst,
  ChevronLast,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Keyboard,
} from 'lucide-react'
import { useState } from 'react'

interface Props {
  onFirst: () => void
  onBack: () => void
  onForward: () => void
  onLast: () => void
  onNextError: (() => void) | null // null = no more errors of the user
}

const SHORTCUTS: [string, string][] = [
  ['← →', 'Jugada anterior / siguiente'],
  ['Inicio · Fin', 'Principio / final'],
  ['N', 'Siguiente error tuyo'],
  ['Esc', 'Volver a la partida'],
]

export function NavBar({ onFirst, onBack, onForward, onLast, onNextError }: Props) {
  const [help, setHelp] = useState(false)
  return (
    <div className="relative flex items-center gap-1.5" aria-label="Navegación" role="group">
      <button
        type="button"
        className="btn-icon h-9 w-9"
        aria-label="Principio"
        title="Principio (Inicio)"
        onClick={onFirst}
      >
        <ChevronFirst size={20} />
      </button>
      <button
        type="button"
        className="btn-icon h-9 w-9"
        aria-label="Anterior"
        title="Anterior (←)"
        onClick={onBack}
      >
        <ChevronLeft size={20} />
      </button>
      <button
        type="button"
        className="btn-icon h-9 w-9"
        aria-label="Siguiente"
        title="Siguiente (→)"
        onClick={onForward}
      >
        <ChevronRight size={20} />
      </button>
      <button
        type="button"
        className="btn-icon h-9 w-9"
        aria-label="Final"
        title="Final (Fin)"
        onClick={onLast}
      >
        <ChevronLast size={20} />
      </button>
      <button
        type="button"
        className="btn ml-auto h-9 px-2.5"
        disabled={onNextError === null}
        onClick={onNextError ?? undefined}
        title="Siguiente error (N)"
      >
        <CircleAlert size={16} />
        Siguiente error
      </button>
      <button
        type="button"
        className="btn-icon h-9 w-9"
        aria-label="Atajos de teclado"
        aria-expanded={help}
        onClick={() => {
          setHelp((h) => !h)
        }}
      >
        <Keyboard size={18} />
      </button>
      {help && (
        <div
          role="dialog"
          aria-label="Atajos de teclado"
          className="panel absolute right-0 bottom-12 z-20 w-64 p-3 text-sm shadow-xl"
        >
          <ul className="flex flex-col gap-1.5">
            {SHORTCUTS.map(([keys, what]) => (
              <li key={keys} className="flex justify-between gap-3">
                <kbd className="rounded bg-panel-2 px-1.5 font-mono text-xs leading-5">{keys}</kbd>
                <span className="text-muted">{what}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
