import { ExternalLink, Pause, Play, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { gamesApi, type GameFilters, type GamePage, type GameSummary } from '../../api/games'
import { syncApi, type QueueState } from '../../api/sync'
import { AnalyzeButton } from '../play/AnalyzeButton'
import { COLOR_LABEL, outcomeShortText } from '../play/gameText'
import { SyncProgress } from '../sync/SyncProgress'
import { PLATFORM_LABEL, useSync } from '../sync/useSync'

const PAGE_SIZE = 50
const QUEUE_POLL_MS = 3000

const TIME_CLASS_LABEL = {
  bullet: 'Bala',
  blitz: 'Blitz',
  rapid: 'Rápida',
  classical: 'Clásica',
  correspondence: 'Correspondencia',
} as const

function player(name: string | null, elo: number | null, fallback: string): string {
  return `${name ?? fallback}${elo ? ` (${String(elo)})` : ''}`
}

function title(g: GameSummary): string {
  if (g.source === 'imported') {
    return `${player(g.white_name, g.white_elo, 'Blancas')} – ${player(g.black_name, g.black_elo, 'Negras')}`
  }
  return `vs Stockfish (${g.bot_level_label ?? '?'})`
}

function origin(g: GameSummary): string {
  if (g.platform) return PLATFORM_LABEL[g.platform]
  return g.source === 'imported' ? 'PGN' : 'Bot'
}

/** Filters <-> URL search params (so the page can be shared and comes back as it was). */
const FILTERS = {
  origin: {
    label: 'Origen',
    options: [
      ['lichess', 'Lichess'],
      ['chesscom', 'Chess.com'],
      ['pgn', 'PGN'],
      ['bot', 'Contra el bot'],
    ],
  },
  time_class: { label: 'Ritmo', options: Object.entries(TIME_CLASS_LABEL) },
  result: {
    label: 'Resultado',
    options: [
      ['win', 'Victorias'],
      ['draw', 'Tablas'],
      ['loss', 'Derrotas'],
    ],
  },
  color: {
    label: 'Color',
    options: [
      ['white', 'Blancas'],
      ['black', 'Negras'],
    ],
  },
  analysed: {
    label: 'Análisis',
    options: [
      ['true', 'Analizadas'],
      ['false', 'Sin analizar'],
    ],
  },
} as const

type FilterKey = keyof typeof FILTERS

function toFilters(params: URLSearchParams): GameFilters {
  const filters: GameFilters = {}
  const origin = params.get('origin')
  if (origin === 'bot') filters.source = 'played'
  else if (origin === 'lichess' || origin === 'chesscom' || origin === 'pgn')
    filters.platform = origin
  const timeClass = params.get('time_class')
  if (timeClass && timeClass in TIME_CLASS_LABEL)
    filters.time_class = timeClass as keyof typeof TIME_CLASS_LABEL
  const result = params.get('result')
  if (result === 'win' || result === 'draw' || result === 'loss') filters.result = result
  const color = params.get('color')
  if (color === 'white' || color === 'black') filters.color = color
  const analysed = params.get('analysed')
  if (analysed === 'true' || analysed === 'false') filters.analysed = analysed === 'true'
  return filters
}

/** Background analysis of synchronised games: progress and pause/resume. */
function QueueBar({ queue, onToggle }: { queue: QueueState; onToggle: () => void }) {
  if (!queue.enabled || (queue.pending === 0 && queue.failed === 0)) return null
  return (
    <div
      role="status"
      aria-label="Análisis automático"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-panel-2/60 px-3 py-2 text-sm"
    >
      <span>
        Análisis automático:{' '}
        {queue.pending > 0
          ? `${String(queue.pending)} pendientes${queue.paused ? ' (en pausa)' : queue.current_game_id ? ' · analizando…' : ''}`
          : 'al día'}
        {queue.failed > 0 && ` · ${String(queue.failed)} con error`}
      </span>
      {queue.pending > 0 && (
        <button type="button" className="btn ml-auto" onClick={onToggle}>
          {queue.paused ? <Play size={14} /> : <Pause size={14} />}
          {queue.paused ? 'Reanudar' : 'Pausar'}
        </button>
      )}
    </div>
  )
}

export function HistoryPage() {
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState<GamePage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [queue, setQueue] = useState<QueueState | null>(null)
  const offset = Math.max(0, Number(params.get('page') ?? '1') - 1) * PAGE_SIZE
  const query = params.toString()

  const load = useCallback(() => {
    gamesApi
      .list(toFilters(new URLSearchParams(query)), PAGE_SIZE, offset)
      .then(setPage)
      .catch(() => {
        setError('No se pudo cargar el historial.')
      })
  }, [query, offset])
  useEffect(load, [load])
  const sync = useSync(load)

  // Queue status: while games are pending, refresh it (and the list, for their status).
  const pending = queue?.pending ?? 0
  useEffect(() => {
    syncApi
      .queue()
      .then(setQueue)
      .catch(() => {
        // Optional.
      })
  }, [])
  useEffect(() => {
    if (pending === 0 && !(sync.state?.running ?? false)) return
    const timer = window.setInterval(() => {
      syncApi
        .queue()
        .then((next) => {
          setQueue((before) => {
            if (before && before.pending !== next.pending) load()
            return next
          })
        })
        .catch(() => {
          // Try again on the next tick.
        })
    }, QUEUE_POLL_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [pending, sync.state?.running, load])

  const setFilter = (key: FilterKey, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('page')
    setParams(next)
  }
  const goTo = (n: number) => {
    const next = new URLSearchParams(params)
    next.set('page', String(n))
    setParams(next)
  }

  if (error) return <p className="text-danger">{error}</p>
  const running = sync.state?.running ?? false
  const pageNumber = offset / PAGE_SIZE + 1
  const pages = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1

  return (
    <div className="panel flex flex-col gap-3 p-2 sm:p-3">
      <div className="flex flex-wrap items-center gap-2 px-1 pt-1">
        <h2 className="text-lg font-semibold">Historial</h2>
        <button
          type="button"
          className="btn ml-auto"
          disabled={running}
          onClick={() => {
            sync.start()
          }}
        >
          <RefreshCw size={14} className={running ? 'animate-spin' : ''} />
          {running ? 'Sincronizando…' : 'Sincronizar'}
        </button>
      </div>
      {sync.error && (
        <p role="alert" className="px-1 text-sm text-danger">
          {sync.error}{' '}
          {sync.error.includes('Ajustes') && (
            <Link className="text-accent-strong underline" to="/settings">
              Ir a Ajustes
            </Link>
          )}
        </p>
      )}
      {sync.state && !sync.state.older && (running || sync.state.finished_at) && (
        <div className="px-1">
          <SyncProgress state={sync.state} />
        </div>
      )}
      {queue && (
        <QueueBar
          queue={queue}
          onToggle={() => {
            ;(queue.paused ? syncApi.resume() : syncApi.pause()).then(setQueue).catch(() => {
              // The button can be pressed again.
            })
          }}
        />
      )}

      <div role="group" aria-label="Filtros" className="flex flex-wrap gap-2 px-1">
        {(Object.keys(FILTERS) as FilterKey[]).map((key) => (
          <label key={key} className="flex items-center gap-1 text-sm">
            <span className="sr-only">{FILTERS[key].label}</span>
            <select
              className="field py-1 text-sm"
              aria-label={FILTERS[key].label}
              value={params.get(key) ?? ''}
              onChange={(e) => {
                setFilter(key, e.target.value)
              }}
            >
              <option value="">{FILTERS[key].label}: todas</option>
              {FILTERS[key].options.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      {!page ? (
        <p className="px-1 text-muted">Cargando…</p>
      ) : page.total === 0 ? (
        <p className="px-1">
          {query ? (
            'Ninguna partida con estos filtros.'
          ) : (
            <>
              Aún no hay partidas. <Link to="/">Juega una</Link>,{' '}
              <Link to="/import">importa un PGN</Link> o sincroniza tus cuentas de{' '}
              <Link to="/settings">Lichess y Chess.com</Link>.
            </>
          )}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th>Partida</th>
                <th className="hidden sm:table-cell">Origen</th>
                <th className="hidden sm:table-cell">Ritmo</th>
                <th className="hidden sm:table-cell">Tu color</th>
                <th className="hidden sm:table-cell">Resultado</th>
                <th className="hidden sm:table-cell">Jugadas</th>
                <th>Revisión</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {page.items.map((g) => {
                const ongoing = g.result === null
                return (
                  <tr key={g.id} className="border-b border-line">
                    <td className="px-2 py-2.5 align-top whitespace-nowrap sm:px-3 sm:align-middle">
                      {new Date(g.played_at ?? g.created_at).toLocaleString('es-ES', {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })}
                    </td>
                    <td className="py-2 sm:min-w-48">
                      {title(g)}
                      {/* Mobile: the hidden columns, in one line. */}
                      <span className="block text-xs text-muted sm:hidden">
                        {[
                          origin(g),
                          g.time_class ? TIME_CLASS_LABEL[g.time_class] : null,
                          outcomeShortText(g.result, g.player_color),
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                    </td>
                    <td className="hidden sm:table-cell">
                      <span className="rounded-md bg-panel-2 px-1.5 py-0.5 text-xs whitespace-nowrap text-muted">
                        {origin(g)}
                      </span>
                    </td>
                    <td className="hidden sm:table-cell">
                      {g.time_class ? TIME_CLASS_LABEL[g.time_class] : '—'}
                    </td>
                    <td className="hidden sm:table-cell">{COLOR_LABEL[g.player_color]}</td>
                    <td className="hidden sm:table-cell">
                      {outcomeShortText(g.result, g.player_color)}
                    </td>
                    <td className="hidden sm:table-cell">{Math.ceil(g.move_count / 2)}</td>
                    <td>
                      {ongoing ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <AnalyzeButton game={g} compact />
                      )}
                    </td>
                    <td className="pr-2 whitespace-nowrap">
                      {g.source === 'played' && (
                        <Link
                          className="text-accent-strong hover:underline"
                          to={`/play/${String(g.id)}`}
                        >
                          {ongoing ? 'Continuar' : 'Ver partida'}
                        </Link>
                      )}
                      {g.external_url && (
                        <a
                          className="inline-flex items-center gap-1 text-muted hover:text-fg"
                          href={g.external_url}
                          target="_blank"
                          rel="noreferrer"
                          title={`Ver en ${origin(g)}`}
                        >
                          <ExternalLink size={14} />
                          <span className="sr-only">Ver en {origin(g)}</span>
                        </a>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {page && pages > 1 && (
        <nav aria-label="Páginas" className="flex items-center justify-center gap-2 pb-1 text-sm">
          <button
            type="button"
            className="btn"
            disabled={pageNumber <= 1}
            onClick={() => {
              goTo(pageNumber - 1)
            }}
          >
            Anterior
          </button>
          <span className="tabular text-muted">
            {pageNumber} / {pages} · {page.total} partidas
          </span>
          <button
            type="button"
            className="btn"
            disabled={pageNumber >= pages}
            onClick={() => {
              goTo(pageNumber + 1)
            }}
          >
            Siguiente
          </button>
        </nav>
      )}
    </div>
  )
}
