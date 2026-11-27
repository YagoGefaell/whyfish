import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

export type SaveStatus = { state: 'idle' | 'saving' | 'saved' } | { state: 'error'; text: string }

/**
 * Saving settings without a button (phase 6.5): `schedule()` saves after a short pause (typing),
 * `flush()` saves now (leaving a field, a checkbox). `save` returns a promise; its rejection
 * message is shown. Pending saves run on unmount so nothing is lost when leaving the page.
 */
export function useAutoSave(save: () => Promise<unknown>, delayMs: number) {
  const [status, setStatus] = useState<SaveStatus>({ state: 'idle' })
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latest = useRef(save)
  useLayoutEffect(() => {
    latest.current = save
  })

  const flush = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
    setStatus({ state: 'saving' })
    latest
      .current()
      .then(() => {
        setStatus({ state: 'saved' })
      })
      .catch((err: unknown) => {
        setStatus({
          state: 'error',
          text: err instanceof Error && err.message ? err.message : 'No se pudo guardar.',
        })
      })
  }, [])

  const schedule = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(flush, delayMs)
  }, [delayMs, flush])

  useEffect(
    () => () => {
      if (timer.current) {
        clearTimeout(timer.current)
        void latest.current().catch(() => undefined)
      }
    },
    [],
  )

  return { status, schedule, flush }
}
