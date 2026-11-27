import type { SyncState } from '../../api/sync'
import { PLATFORM_LABEL } from './useSync'

const STATE = { waiting: 'en espera', running: 'importando…', done: 'hecho', error: 'error' }

/** Progress of a sync, one line per account. */
export function SyncProgress({ state }: { state: SyncState }) {
  return (
    <ul aria-label="Sincronización" aria-live="polite" className="flex flex-col gap-1 text-sm">
      {state.accounts.map((a) => (
        <li key={a.platform}>
          <span className="font-medium">{PLATFORM_LABEL[a.platform]}</span> ({a.username}):{' '}
          {STATE[a.state]} · {a.imported} nuevas
          {a.error && <span className="block text-danger">{a.error}</span>}
        </li>
      ))}
    </ul>
  )
}
