import { History, Save } from 'lucide-react'
import { useEffect, useState, type SyntheticEvent } from 'react'
import { ApiError } from '../../api/client'
import { syncApi, type Account, type Accounts } from '../../api/sync'
import { PLATFORM_LABEL, useSync } from '../sync/useSync'
import { SyncProgress } from '../sync/SyncProgress'

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

/** Ajustes: Lichess / Chess.com accounts (phase 6a). */
export function SettingsPage() {
  const [data, setData] = useState<Accounts | null>(null)
  const [lichess, setLichess] = useState('')
  const [chesscom, setChesscom] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  const load = (accounts: Accounts) => {
    setData(accounts)
    setLichess(accounts.accounts.find((a) => a.platform === 'lichess')?.username ?? '')
    setChesscom(accounts.accounts.find((a) => a.platform === 'chesscom')?.username ?? '')
  }
  const reload = () => {
    syncApi
      .accounts()
      .then(load)
      .catch(() => {
        setMessage({ ok: false, text: 'No se pudieron cargar los ajustes.' })
      })
  }
  useEffect(reload, [])
  const sync = useSync(reload)

  const save = (event: SyntheticEvent) => {
    event.preventDefault()
    setSaving(true)
    setMessage(null)
    syncApi
      .saveAccounts(lichess, chesscom)
      .then((accounts) => {
        load(accounts)
        setMessage({ ok: true, text: 'Cuentas guardadas.' })
      })
      .catch((err: unknown) => {
        setMessage({
          ok: false,
          text: err instanceof ApiError ? err.message : 'No se pudieron guardar.',
        })
      })
      .finally(() => {
        setSaving(false)
      })
  }

  if (!data) return <p className="text-muted">Cargando ajustes…</p>
  const account = (platform: Account['platform']) =>
    data.accounts.find((a) => a.platform === platform)
  const running = sync.state?.running ?? false

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <form onSubmit={save} className="panel flex flex-col gap-4 p-6">
        <h2 className="text-xl font-semibold">Ajustes</h2>
        <section className="flex flex-col gap-3">
          <h3 className="font-semibold">Tus cuentas</h3>
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
                    value={platform === 'lichess' ? lichess : chesscom}
                    onChange={(e) => {
                      ;(platform === 'lichess' ? setLichess : setChesscom)(e.target.value)
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
        {message && (
          <p role={message.ok ? 'status' : 'alert'} className={message.ok ? '' : 'text-danger'}>
            {message.text}
          </p>
        )}
        <button type="submit" className="btn-primary self-start" disabled={saving || running}>
          <Save size={16} /> Guardar
        </button>
      </form>

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
