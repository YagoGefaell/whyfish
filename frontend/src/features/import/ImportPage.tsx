import { useState, type ChangeEvent, type SyntheticEvent } from 'react'
import { useNavigate } from 'react-router'
import { analysisApi } from '../../api/analysis'
import { ApiError, isRecord } from '../../api/client'
import { gamesApi, type Color } from '../../api/games'

type ColorChoice = Color | 'auto'

interface ColorQuestion {
  white: string | null
  black: string | null
}

const COLOR_OPTIONS: readonly (readonly [ColorChoice, string])[] = [
  ['auto', 'Detectar por mi nombre'],
  ['white', 'Blancas'],
  ['black', 'Negras'],
]

export function ImportPage() {
  const navigate = useNavigate()
  const [pgn, setPgn] = useState('')
  const [color, setColor] = useState<ColorChoice>('auto')
  const [question, setQuestion] = useState<ColorQuestion | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = (userColor: Color | null) => {
    setBusy(true)
    setError(null)
    gamesApi
      .importPgn(pgn, userColor)
      .then(async ({ game, warnings }) => {
        await analysisApi.start(game.id)
        await navigate(`/review/${String(game.id)}`, { state: { warnings } })
      })
      .catch((err: unknown) => {
        setBusy(false)
        if (
          err instanceof ApiError &&
          isRecord(err.detail) &&
          err.detail.code === 'color_required'
        ) {
          const d = err.detail
          setQuestion({
            white: typeof d.white === 'string' ? d.white : null,
            black: typeof d.black === 'string' ? d.black : null,
          })
          return
        }
        setError(err instanceof ApiError ? err.message : 'No se pudo importar la partida.')
      })
  }

  const onSubmit = (event: SyntheticEvent) => {
    event.preventDefault()
    setQuestion(null)
    submit(color === 'auto' ? null : color)
  }

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    file
      .text()
      .then(setPgn)
      .catch(() => {
        setError('No se pudo leer el archivo.')
      })
  }

  return (
    <form onSubmit={onSubmit} className="panel mx-auto flex w-full max-w-2xl flex-col gap-4 p-6">
      <h2 className="text-xl font-semibold">Importar partida (PGN)</h2>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Pega el PGN</span>
        <textarea
          value={pgn}
          onChange={(e) => {
            setPgn(e.target.value)
            setQuestion(null)
          }}
          rows={10}
          spellCheck={false}
          placeholder={'[White "…"]\n[Black "…"]\n\n1. e4 e5 2. Nf3 …'}
          className="field font-mono text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span>…o sube un archivo .pgn</span>
        <input type="file" accept=".pgn,text/plain" onChange={onFile} />
      </label>
      <fieldset>
        <legend className="mb-1 font-medium">¿Con qué color jugabas?</legend>
        <div className="flex flex-wrap gap-4">
          {COLOR_OPTIONS.map(([value, label]) => (
            <label key={value} className="flex items-center gap-1">
              <input
                type="radio"
                name="color"
                value={value}
                checked={color === value}
                onChange={() => {
                  setColor(value)
                }}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      {question && (
        <div
          role="alertdialog"
          aria-label="¿Quién eras tú?"
          className="rounded-xl border border-warn/40 bg-warn/10 p-3"
        >
          <p className="mb-2 font-medium">No he podido deducir tu color. ¿Quién eras tú?</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                submit('white')
              }}
              className="btn"
            >
              Blancas{question.white ? `: ${question.white}` : ''}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                submit('black')
              }}
              className="btn"
            >
              Negras{question.black ? `: ${question.black}` : ''}
            </button>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}

      <button type="submit" disabled={busy || pgn.trim() === ''} className="btn-primary self-start">
        {busy ? 'Importando…' : 'Importar y analizar'}
      </button>
    </form>
  )
}
