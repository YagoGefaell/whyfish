import { History } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { syncApi, type Account, type Accounts } from '../../api/sync'
import { trainingApi, type TrainingSettings } from '../../api/training'
import { PLATFORM_LABEL, useSync } from '../sync/useSync'
import { SyncProgress } from '../sync/SyncProgress'
import { SaveNote } from '../../components/SaveNote'
import { useAutoSave } from '../../lib/useAutoSave'
import { AppearanceSettings } from './AppearanceSettings'

const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('es-ES') : '—')

function AccountStatus({ account }: { account: Account }) {
  return (
    <p className="text-sm text-muted" data-testid={`account-${account.platform}`}>
      {account.last_synced_at ? (
        <>
          Partidas desde el {date(account.covered_from)} · {account.imported_count} importadas ·
          última sincronización {new Date(account.last_synced_at).toLocaleString('es-ES')}
        </>
      ) : (
        'Aún no se ha sincronizado.'
      )}
      {account.last_error && (
        <span role="alert" className="block text-danger">
          {account.last_error}
        </span>
      )}
    </p>
  )
}

/** Training settings (phase 6c): saved when changed (numbers after a short pause). */
function TrainingSettingsForm() {
  const [s, setS] = useState<TrainingSettings | null>(null)
  const value = useRef<TrainingSettings | null>(null)
  const { status, schedule, flush } = useAutoSave(async () => {
    if (value.current) await trainingApi.saveSettings(value.current)
  }, 600)
  useEffect(() => {
    trainingApi
      .settings()
      .then((loaded) => {
        value.current = loaded
        setS(loaded)
      })
      .catch(() => {
        // The section stays hidden.
      })
  }, [])
  if (!s) return null
  const change = (next: TrainingSettings, now: boolean) => {
    value.current = next
    setS(next)
    if (now) flush()
    else schedule()
  }
  return (
    <section className="panel flex flex-col gap-3 p-6" aria-label="Entrenamiento">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-semibold">Entrenamiento</h3>
        <SaveNote status={status} />
      </div>
      <label className="flex items-center justify-between gap-3">
        <span>Ejercicios por sesión diaria</span>
        <input
          type="number"
          min={1}
          max={20}
          className="field w-20"
          value={s.session_size}
          onChange={(e) => {
            change({ ...s, session_size: Number(e.target.value) }, false)
          }}
        />
      </label>
      <label className="flex items-center justify-between gap-3">
        <span>Nuevos de tus puntos débiles (por sesión)</span>
        <input
          type="number"
          min={0}
          max={20}
          className="field w-20"
          value={s.weak_new}
          onChange={(e) => {
            change({ ...s, weak_new: Number(e.target.value) }, false)
          }}
        />
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={s.include_bullet}
          onChange={(e) => {
            change({ ...s, include_bullet: e.target.checked }, true)
          }}
        />
        Incluir errores de partidas bala
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={s.include_bot}
          onChange={(e) => {
            change({ ...s, include_bot: e.target.checked }, true)
          }}
        />
        <span>
          Incluir partidas contra el bot{' '}
          <span className="text-sm text-muted">
            (solo cuando no quedan ejercicios de tus partidas reales)
          </span>
        </span>
      </label>
    </section>
  )
}

/** Ajustes: accounts (phase 6a), appearance (phase 6.5), training (phase 6c). Everything is
 * saved without a button. */
export function SettingsPage() {
  const [data, setData] = useState<Accounts | null>(null)
  const [names, setNames] = useState({ lichess: '', chesscom: '' })
  const [loadError, setLoadError] = useState(false)
  // What the backend has: an account is validated and saved only when its value changed.
  const saved = useRef({ lichess: '', chesscom: '' })
  const typed = useRef(names)

  const load = (accounts: Accounts) => {
    const next = {
      lichess: accounts.accounts.find((a) => a.platform === 'lichess')?.username ?? '',
      chesscom: accounts.accounts.find((a) => a.platform === 'chesscom')?.username ?? '',
    }
    // A field the user has edited since the last save keeps what is typed; the rest take the
    // backend's value.
    const before = saved.current
    const edited = (key: 'lichess' | 'chesscom') =>
      typed.current[key].trim() !== before[key] && typed.current[key].trim() !== next[key]
    const merged = {
      lichess: edited('lichess') ? typed.current.lichess : next.lichess,
      chesscom: edited('chesscom') ? typed.current.chesscom : next.chesscom,
    }
    saved.current = next
    typed.current = merged
    setNames(merged)
    setData(accounts)
  }
  const reload = () => {
    syncApi
      .accounts()
      .then(load)
      .catch(() => {
        setLoadError(true)
      })
  }
  useEffect(reload, [])
  const sync = useSync(reload)

  const changed = () =>
    typed.current.lichess.trim() !== saved.current.lichess ||
    typed.current.chesscom.trim() !== saved.current.chesscom
  const accounts = useAutoSave(async () => {
    if (!changed()) return
    const { lichess, chesscom } = typed.current
    load(await syncApi.saveAccounts(lichess.trim(), chesscom.trim()))
  }, 1200)

  if (loadError && !data) return <p className="text-danger">No se pudieron cargar los ajustes.</p>
  if (!data) return <p className="text-muted">Cargando ajustes…</p>
  const account = (platform: Account['platform']) =>
    data.accounts.find((a) => a.platform === platform)
  const running = sync.state?.running ?? false

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <h2 className="text-xl font-semibold">Ajustes</h2>
      <section className="panel flex flex-col gap-3 p-6" aria-label="Tus cuentas">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-semibold">Tus cuentas</h3>
          <SaveNote status={accounts.status} />
        </div>
        <p className="text-sm text-muted">
          Tus partidas de Lichess y Chess.com se importan desde el Historial («Sincronizar»). La
          primera vez, las de los últimos {data.sync_months} meses.
        </p>
        {(['lichess', 'chesscom'] as const).map((platform) => {
          const current = account(platform)
          return (
            <div key={platform} className="flex flex-col gap-1">
              <label className="flex flex-col gap-1">
                <span className="font-medium">Usuario de {PLATFORM_LABEL[platform]}</span>
                <input
                  className="field"
                  value={names[platform]}
                  disabled={running}
                  onChange={(e) => {
                    const next = { ...typed.current, [platform]: e.target.value }
                    typed.current = next
                    setNames(next)
                    if (changed()) accounts.schedule()
                  }}
                  onBlur={() => {
                    if (changed()) accounts.flush()
                  }}
                  placeholder="Sin cuenta"
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              {current && <AccountStatus account={current} />}
            </div>
          )
        })}
      </section>

      <AppearanceSettings />

      <TrainingSettingsForm />

      {data.accounts.length > 0 && (
        <section className="panel flex flex-col gap-3 p-6">
          <h3 className="font-semibold">Partidas más antiguas</h3>
          <p className="text-sm text-muted">
            Amplía hacia atrás {data.sync_months} meses más el rango de partidas importadas.
          </p>
          <button
            type="button"
            className="btn self-start"
            disabled={running}
            onClick={() => {
              sync.start(true)
            }}
          >
            <History size={16} /> Importar partidas más antiguas
          </button>
          {sync.error && (
            <p role="alert" className="text-danger">
              {sync.error}
            </p>
          )}
          {sync.state?.older && <SyncProgress state={sync.state} />}
        </section>
      )}
    </div>
  )
}
