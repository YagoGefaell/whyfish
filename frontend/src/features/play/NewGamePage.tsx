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
    gamesApi
      .create({ color, level, allow_undo: allowUndo, allow_hint: allowHint })
      .then((game) => navigate(`/play/${String(game.id)}`))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'No se pudo crear la partida.')
        setSubmitting(false)
      })
  }

  return (
    <form onSubmit={submit} className="flex max-w-md flex-col gap-5">
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
          className="rounded border border-gray-300 px-2 py-1"
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

      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting || levels.length === 0}
        className="rounded bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800 disabled:opacity-50"
      >
        {submitting ? 'Creando…' : 'Empezar'}
      </button>
    </form>
  )
}
