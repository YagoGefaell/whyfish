import { useEffect, useState, type SyntheticEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError } from '../../api/client'
import { gamesApi, type BotLevel, type ColorChoice, type Level } from '../../api/games'

const COLOR_OPTIONS: { value: ColorChoice; label: string }[] = [
  { value: 'white', label: 'Blancas' },
  { value: 'black', label: 'Negras' },
  { value: 'random', label: 'Aleatorio' },
]

export function NewGamePage() {
  const navigate = useNavigate()
  const [levels, setLevels] = useState<Level[]>([])
  const [color, setColor] = useState<ColorChoice>('white')
  const [level, setLevel] = useState<BotLevel>('club')
  const [allowUndo, setAllowUndo] = useState(false)
  const [allowHint, setAllowHint] = useState(false)
  const [fen, setFen] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    gamesApi
      .levels()
      .then(setLevels)
      .catch(() => {
        setError('No se pudieron cargar los niveles.')
      })
  }, [])

  const submit = (event: SyntheticEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const createdAt = Date.now()
    gamesApi
      .create({
        color,
        level,
        allow_undo: allowUndo,
        allow_hint: allowHint,
        fen: fen.trim() || null,
      })
      // `createdAt`: if the bot opens (user with black), the play page shows its minimum
      // "thinking" time, minus what the creation already took (SPEC §1.1).
      .then((game) => navigate(`/play/${String(game.id)}`, { state: { createdAt } }))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'No se pudo crear la partida.')
        setSubmitting(false)
      })
  }

  return (
    <form onSubmit={submit} className="panel mx-auto flex w-full max-w-lg flex-col gap-5 p-6">
      <h2 className="text-xl font-semibold">Nueva partida</h2>

      <fieldset>
        <legend className="mb-1 font-medium">Tu color</legend>
        <div className="flex gap-4">
          {COLOR_OPTIONS.map((option) => (
            <label key={option.value} className="flex items-center gap-1">
              <input
                type="radio"
                name="color"
                value={option.value}
                checked={color === option.value}
                onChange={() => {
                  setColor(option.value)
                }}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex flex-col gap-1">
        <span className="font-medium">Nivel del bot</span>
        <select
          value={level}
          onChange={(e) => {
            setLevel(e.target.value as BotLevel)
          }}
          className="field"
        >
          {levels.map((lvl) => (
            <option key={lvl.id} value={lvl.id}>
              {lvl.label}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 font-medium">Ayudas (desactivadas por defecto)</legend>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={allowUndo}
            onChange={(e) => {
              setAllowUndo(e.target.checked)
            }}
          />
          Permitir deshacer jugadas
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={allowHint}
            onChange={(e) => {
              setAllowHint(e.target.checked)
            }}
          />
          Permitir pistas (muestra qué pieza mover)
        </label>
      </fieldset>

      <div className="flex flex-col gap-1">
        <label htmlFor="start-fen" className="font-medium">
          Posición inicial (FEN, opcional)
        </label>
        <input
          id="start-fen"
          type="text"
          value={fen}
          onChange={(e) => {
            setFen(e.target.value)
          }}
          placeholder="Vacío = posición inicial normal"
          spellCheck={false}
          aria-describedby="start-fen-help"
          className="field font-mono text-sm"
        />
        <span id="start-fen-help" className="text-xs text-muted">
          Si le toca mover al bot en esa posición, juega él primero.
        </span>
      </div>

      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting || levels.length === 0}
        className="btn-primary py-2.5 text-base"
      >
        {submitting ? 'Creando…' : 'Empezar'}
      </button>
    </form>
  )
}
