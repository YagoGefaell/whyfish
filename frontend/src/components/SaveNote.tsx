import { Check } from 'lucide-react'
import type { SaveStatus } from '../lib/useAutoSave'

/** The discreet "Guardado" next to a settings section title (or the save error). */
export function SaveNote({ status }: { status: SaveStatus }) {
  if (status.state === 'error') {
    return (
      <span role="alert" className="text-sm text-danger">
        {status.text}
      </span>
    )
  }
  return (
    <span role="status" className="inline-flex items-center gap-1 text-xs text-muted">
      {status.state === 'saving' && 'Guardando…'}
      {status.state === 'saved' && (
        <>
          <Check size={13} /> Guardado
        </>
      )}
    </span>
  )
}
