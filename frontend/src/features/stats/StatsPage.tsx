import { ChevronDown, Dumbbell, TriangleAlert } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import type { TimeClass } from '../../api/games'
import { statsApi, type StatsFilters, type StatsResponse } from '../../api/stats'
import { AccuracyChart } from './AccuracyChart'
import { Examples } from './Examples'

const PENDING_POLL_MS = 3000
const TIME_CLASSES: [TimeClass, string][] = [
  ['bullet', 'Bala'],
  ['blitz', 'Blitz'],
  ['rapid', 'Rápida'],
  ['classical', 'Clásica'],
  ['correspondence', 'Correspondencia'],
]
const PERIODS: [string, string][] = [
  ['30', 'Último mes'],
  ['90', 'Últimos 3 meses'],
  ['365', 'Último año'],
]

function toFilters(params: URLSearchParams): StatsFilters {
  const filters: StatsFilters = {}
  if (params.get('bot') === '1') filters.include_bot = true
  const timeClass = params.get('time_class')
  const known = TIME_CLASSES.find(([value]) => value === timeClass)
  if (known) filters.time_class = known[0]
  const color = params.get('color')
  if (color === 'white' || color === 'black') filters.color = color
  const days = Number(params.get('days'))
  if (days > 0) filters.days = days
  return filters
}

/** A block with a title and, folded, the positions that explain it. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel flex flex-col gap-3 p-4">
      <h3 className="font-semibold">{title}</h3>
      {children}
    </section>
  )
}

function Positions({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center gap-1 text-sm text-accent-strong">
        {label}
        <ChevronDown size={14} className="transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  )
}

function Bar({ value, max }: { value: number; max: number }) {
  return (
    <div className="h-2 w-full rounded-full bg-panel-2" aria-hidden="true">
      <div
        className="h-2 rounded-full bg-heat"
        style={{ width: `${String(max > 0 ? Math.max(4, (100 * value) / max) : 0)}%` }}
      />
    </div>
  )
}

const pct = (rate: number | null) => (rate === null ? '—' : `${(100 * rate).toFixed(1)} %`)

/** Estadísticas (phase 6b): what to improve, with the positions that explain it. */
export function StatsPage() {
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<StatsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const query = params.toString()
  const pending = data?.insights_pending ?? 0

  useEffect(() => {
    const controller = new AbortController()
    const load = () => {
      statsApi
        .get(toFilters(new URLSearchParams(query)), controller.signal)
        .then(setData)
        .catch(() => {
          if (!controller.signal.aborted) setError('No se pudieron cargar las estadísticas.')
        })
    }
    load()
    // While data of analysed games is still being calculated, refresh.
    const timer = pending > 0 ? window.setInterval(load, PENDING_POLL_MS) : undefined
    return () => {
      controller.abort()
      if (timer !== undefined) window.clearInterval(timer)
    }
  }, [query, pending])

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  if (error) return <p className="text-danger">{error}</p>
  if (!data) return <p className="text-muted">Cargando estadísticas…</p>
  const s = data.stats
  const maxPer10 = Math.max(...s.phases.map((p) => p.per10))
  const maxKind = Math.max(0, ...s.kinds.map((k) => k.count))

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-xl font-semibold">Estadísticas</h2>
        <div role="group" aria-label="Filtros" className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={params.get('bot') === '1'}
              onChange={(e) => {
                set('bot', e.target.checked ? '1' : '')
              }}
            />
            Incluir partidas contra el bot
          </label>
          <select
            aria-label="Ritmo"
            className="field py-1 text-sm"
            value={params.get('time_class') ?? ''}
            onChange={(e) => {
              set('time_class', e.target.value)
            }}
          >
            <option value="">Ritmo: todos</option>
            {TIME_CLASSES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Color"
            className="field py-1 text-sm"
            value={params.get('color') ?? ''}
            onChange={(e) => {
              set('color', e.target.value)
            }}
          >
            <option value="">Color: ambos</option>
            <option value="white">Blancas</option>
            <option value="black">Negras</option>
          </select>
          <select
            aria-label="Periodo"
            className="field py-1 text-sm"
            value={params.get('days') ?? ''}
            onChange={(e) => {
              set('days', e.target.value)
            }}
          >
            <option value="">Siempre</option>
            {PERIODS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div role="status" aria-label="Partidas analizadas" className="text-sm">
        <p>
          Basado en <strong>{s.games}</strong>{' '}
          {s.games === 1 ? 'partida analizada' : 'partidas analizadas'}
          {params.get('bot') === '1' ? '' : ' (solo partidas reales: Lichess, Chess.com y PGN)'}.
          {data.games_unanalysed > 0 &&
            ` ${String(data.games_unanalysed)} más aún sin analizar: la cola las irá analizando.`}
          {pending > 0 && ` Calculando los datos de ${String(pending)}…`}
        </p>
        {!s.enough && (
          <p className="mt-1 flex items-center gap-1.5 text-warn">
            <TriangleAlert size={16} /> Son pocas para sacar conclusiones fiables (al menos{' '}
            {s.min_games}).
          </p>
        )}
      </div>

      {s.games === 0 ? (
        <p className="panel p-4">
          Aún no hay partidas analizadas con estos filtros.{' '}
          <Link className="text-accent-strong underline" to="/games">
            Ve al Historial
          </Link>{' '}
          para sincronizar o analizar tus partidas.
        </p>
      ) : (
        <>
          <Section title="Tus 3 puntos débiles">
            {s.weak_points.length === 0 ? (
              <p className="text-sm text-muted">No destaca ningún punto débil con estos datos.</p>
            ) : (
              <ol className="grid gap-3 md:grid-cols-3">
                {s.weak_points.map((w, i) => (
                  <li
                    key={w.key}
                    className="flex flex-col gap-2 rounded-lg border border-line bg-panel-2/40 p-3"
                  >
                    <h4 className="font-semibold">
                      {i + 1}. {w.title}
                    </h4>
                    <p className="text-sm">{w.text}</p>
                    <p className="text-sm text-muted">{w.advice}</p>
                    <Positions label="Ver ejemplos">
                      <Examples examples={w.examples.slice(0, 5)} label={`Ejemplos: ${w.title}`} />
                    </Positions>
                    {Object.keys(w.train).length > 0 && (
                      <Link
                        className="btn self-start"
                        to={`/train?${new URLSearchParams(w.train).toString()}`}
                      >
                        <Dumbbell size={14} /> Entrenar esto
                      </Link>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Section>

          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Precisión">
              <p className="text-sm">
                Media:{' '}
                <strong className="tabular">
                  {s.accuracy_mean === null ? '—' : `${s.accuracy_mean.toFixed(1)} %`}
                </strong>{' '}
                <span className="text-muted">
                  · la línea verde es la media de las últimas partidas; cada punto, una partida.
                </span>
              </p>
              <AccuracyChart points={s.accuracy} />
            </Section>

            <Section title="Errores por fase">
              <p className="text-sm text-muted">Errores (?, ?? y ✗) cada 10 jugadas tuyas.</p>
              <ul className="flex flex-col gap-3">
                {s.phases.map((p) => (
                  <li key={p.phase} className="flex flex-col gap-1">
                    <div className="flex items-baseline justify-between text-sm">
                      <span>{p.label}</span>
                      <span className="tabular">
                        {p.per10.toFixed(1)}{' '}
                        <span className="text-muted">
                          ({p.errors} en {p.moves} jugadas)
                        </span>
                      </span>
                    </div>
                    <Bar value={p.per10} max={maxPer10} />
                    {p.errors > 0 && (
                      <Positions label="Ver posiciones">
                        <Examples examples={p.examples} label={`Errores: ${p.label}`} />
                      </Positions>
                    )}
                  </li>
                ))}
              </ul>
            </Section>

            <Section title="Tipos de error más frecuentes">
              {s.kinds.length === 0 ? (
                <p className="text-sm text-muted">Ningún error (?, ?? o ✗). ¡Bien!</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {s.kinds.map((k) => (
                    <li key={k.kind} className="flex flex-col gap-1">
                      <div className="flex items-baseline justify-between text-sm">
                        <span>{k.label}</span>
                        <span className="tabular">{k.count}</span>
                      </div>
                      <Bar value={k.count} max={maxKind} />
                      <Positions label="Ver posiciones">
                        <Examples examples={k.examples} label={`Errores: ${k.label}`} />
                      </Positions>
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            <Section title="Errores con poco tiempo">
              {s.time.games_with_clock === 0 ? (
                <p className="text-sm text-muted">Estas partidas no tienen datos de reloj.</p>
              ) : (
                <>
                  <p className="text-sm">
                    {s.time.low_moves === 0 ? (
                      <>
                        No has jugado ninguna jugada con poco reloj; con tiempo,{' '}
                        <strong>{pct(s.time.normal_rate)}</strong> de tus jugadas son errores.
                      </>
                    ) : (
                      <>
                        Con poco reloj, <strong>{pct(s.time.low_rate)}</strong> de tus jugadas son
                        errores ({s.time.low_errors} de {s.time.low_moves}); con tiempo,{' '}
                        <strong>{pct(s.time.normal_rate)}</strong>.
                      </>
                    )}
                    {s.time.stands_out && (
                      <span className="text-warn"> El reloj te está costando partidas.</span>
                    )}
                  </p>
                  <p className="text-xs text-muted">
                    Poco tiempo: menos de 30 s o del 10 % del tiempo inicial (lo menor). En{' '}
                    {s.time.games_with_clock} partidas con reloj.
                  </p>
                  {s.time.low_errors > 0 && (
                    <Positions label="Ver posiciones">
                      <Examples examples={s.time.examples} label="Errores con poco tiempo" />
                    </Positions>
                  )}
                </>
              )}
            </Section>
          </div>

          <Section title="Aperturas">
            <div className="grid gap-4 md:grid-cols-2">
              {(['white', 'black'] as const).map((color) => {
                const rows = s.openings.filter((o) => o.color === color)
                return (
                  <div key={color} className="overflow-x-auto">
                    <h4 className="mb-1 text-sm font-semibold">
                      Con {color === 'white' ? 'blancas' : 'negras'}
                    </h4>
                    {rows.length === 0 ? (
                      <p className="text-sm text-muted">Sin partidas.</p>
                    ) : (
                      <table className="w-full text-left text-sm">
                        <thead className="text-muted">
                          <tr>
                            <th className="py-1 font-medium">Apertura</th>
                            <th className="font-medium">Partidas</th>
                            <th className="font-medium">V-T-D</th>
                            <th className="font-medium">Puntos</th>
                            <th className="font-medium">Precisión</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((o) => (
                            <tr
                              key={o.family}
                              className={`border-t border-line ${o.worst ? 'text-bad' : ''}`}
                              data-worst={o.worst || undefined}
                            >
                              <td className="py-1.5">
                                <Link
                                  className="hover:underline"
                                  to={`/review/${String(o.game_ids[0])}`}
                                  title="Última partida con esta apertura"
                                >
                                  {o.family}
                                </Link>
                              </td>
                              <td className="tabular">{o.games}</td>
                              <td className="tabular whitespace-nowrap">
                                {o.wins}-{o.draws}-{o.losses}
                              </td>
                              <td className="tabular">{o.score.toFixed(0)} %</td>
                              <td className="tabular">
                                {o.accuracy === null ? '—' : o.accuracy.toFixed(0)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )
              })}
            </div>
            <p className="text-xs text-muted">
              En rojo, las peores (al menos 3 partidas y menos del 50 % de los puntos).
            </p>
          </Section>
        </>
      )}
    </div>
  )
}
