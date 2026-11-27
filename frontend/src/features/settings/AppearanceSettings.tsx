import { useState, type ReactNode } from 'react'
import type { BoardTheme, ColorMode, PieceSet, UiSettings } from '../../api/ui'
import { uiApi } from '../../api/ui'
import { pieceUrl } from '../../components/board/pieceUrls'
import { BOARDS, BOARD_LABEL, PIECE_LABEL, PIECE_SETS, setPrefs, usePrefs } from '../../theme/prefs'
import { ReviewBoard } from '../review/ReviewBoard'

const MODES: { value: ColorMode; label: string }[] = [
  { value: 'system', label: 'Según el sistema' },
  { value: 'light', label: 'Claro' },
  { value: 'dark', label: 'Oscuro' },
]

/**
 * Preview: 1.e4 e5 2.Bc4 Bc5 3.Bxf7+?? (the bishop is lost to Kxf7). It shows the classified
 * move with its badge, the check, the best move (Nf3) and the refutation as arrows.
 */
const PREVIEW_FEN = 'rnbqk1nr/pppp1Bpp/8/2b1p3/4P3/8/PPPP1PPP/RNBQK1NR b KQkq - 0 3'
const PREVIEW_MOVE = { from: 'c4', to: 'f7', classification: 'blunder' as const }
const PREVIEW_ARROWS = [
  { from: 'g1', to: 'f3', color: 'var(--color-arrow-best)' },
  { from: 'e8', to: 'f7', color: 'var(--color-arrow-threat)' },
]

/** Two squares of a board, for its option. */
function BoardSwatch({ board }: { board: BoardTheme }) {
  return (
    <span data-board={board} className="grid h-7 w-14 grid-cols-2 overflow-hidden rounded-md">
      <span style={{ background: 'var(--color-board-light)' }} />
      <span style={{ background: 'var(--color-board-dark)' }} />
    </span>
  )
}

function Option({
  name,
  checked,
  onChange,
  children,
  testId,
}: {
  name: string
  checked: boolean
  onChange: () => void
  children: ReactNode
  testId?: string
}) {
  return (
    <label
      data-testid={testId}
      className={`flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm transition-colors ${
        checked ? 'border-accent bg-selected' : 'border-line hover:bg-hover'
      }`}
    >
      <input type="radio" name={name} checked={checked} onChange={onChange} className="sr-only" />
      {children}
    </label>
  )
}

/** Ajustes > Apariencia (phase 6.5): colour mode, board and pieces, applied and saved at once. */
export function AppearanceSettings() {
  const current = usePrefs()
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null)

  const choose = (change: Partial<UiSettings>) => {
    const next = { ...current, ...change }
    setPrefs(next)
    setStatus(null)
    uiApi
      .save(next)
      .then(() => {
        setStatus({ ok: true, text: 'Guardado.' })
      })
      .catch(() => {
        setStatus({ ok: false, text: 'No se pudo guardar; se aplica solo en este navegador.' })
      })
  }

  return (
    <section className="panel flex flex-col gap-4 p-6" aria-label="Apariencia">
      <h3 className="font-semibold">Apariencia</h3>
      <div className="flex flex-col gap-6 md:flex-row">
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Modo</legend>
            <div className="flex flex-wrap gap-2">
              {MODES.map((m) => (
                <Option
                  key={m.value}
                  name="color-mode"
                  checked={current.color_mode === m.value}
                  onChange={() => {
                    choose({ color_mode: m.value })
                  }}
                >
                  {m.label}
                </Option>
              ))}
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Tablero</legend>
            <div className="flex flex-wrap gap-2">
              {BOARDS.map((board) => (
                <Option
                  key={board}
                  name="board"
                  testId={`board-${board}`}
                  checked={current.board === board}
                  onChange={() => {
                    choose({ board })
                  }}
                >
                  <BoardSwatch board={board} />
                  {BOARD_LABEL[board]}
                </Option>
              ))}
            </div>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Piezas</legend>
            <div className="flex flex-wrap gap-2">
              {PIECE_SETS.map((set: PieceSet) => (
                <Option
                  key={set}
                  name="pieces"
                  testId={`pieces-${set}`}
                  checked={current.pieces === set}
                  onChange={() => {
                    choose({ pieces: set })
                  }}
                >
                  <img src={pieceUrl('wN', set)} alt="" className="h-7 w-7" />
                  <img src={pieceUrl('bQ', set)} alt="" className="-ml-2 h-7 w-7" />
                  {PIECE_LABEL[set]}
                </Option>
              ))}
            </div>
          </fieldset>
          {status && (
            <p
              role={status.ok ? 'status' : 'alert'}
              className={`text-sm ${status.ok ? 'text-muted' : 'text-danger'}`}
            >
              {status.text}
            </p>
          )}
        </div>
        <figure className="flex w-full max-w-[280px] shrink-0 flex-col gap-2 self-center md:self-start">
          <ReviewBoard
            id="preview-board"
            fen={PREVIEW_FEN}
            orientation="white"
            arrows={PREVIEW_ARROWS}
            shownMove={PREVIEW_MOVE}
            animate={false}
            interactive={false}
            onMove={() => {
              // Preview only.
            }}
          />
          <figcaption className="text-xs text-muted">
            Vista previa: 3.Bxf7+?? con la mejor jugada y la refutación.
          </figcaption>
        </figure>
      </div>
    </section>
  )
}
