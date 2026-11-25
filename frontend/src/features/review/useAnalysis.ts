import { useCallback, useEffect, useRef, useState } from 'react'
import { analysisApi, type AnalysisJob, type Review } from '../../api/analysis'
import { ApiError } from '../../api/client'

export type AnalysisPhase =
  | { kind: 'loading' }
  | { kind: 'none' }
  | { kind: 'running'; done: number; total: number }
  | { kind: 'failed'; error: string }
  | { kind: 'ready'; review: Review }
  | { kind: 'error'; message: string }

/** Minimal EventSource surface, so tests can inject a fake. */
export interface EventSourceLike {
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void
  onerror: ((event: Event) => void) | null
  close(): void
}
export type EventSourceFactory = (url: string) => EventSourceLike

const defaultFactory: EventSourceFactory = (url) => new EventSource(url)

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo contactar con el servidor.'
}

/** Analysis status of a game: progress over SSE, then the review. */
export function useAnalysis(gameId: number, factory: EventSourceFactory = defaultFactory) {
  const [phase, setPhase] = useState<AnalysisPhase>({ kind: 'loading' })
  const source = useRef<EventSourceLike | null>(null)
  const alive = useRef(true)
  // Lets the stream's error handler re-subscribe without `follow` referencing itself.
  const followAgain = useRef<() => void>(() => undefined)

  const loadReview = useCallback(() => {
    analysisApi
      .review(gameId)
      .then((review) => {
        if (alive.current) setPhase({ kind: 'ready', review })
      })
      .catch((error: unknown) => {
        if (alive.current) setPhase({ kind: 'error', message: message(error) })
      })
  }, [gameId])

  const apply = useCallback(
    (job: AnalysisJob) => {
      if (job.status === 'done') {
        source.current?.close()
        loadReview()
      } else if (job.status === 'failed') {
        source.current?.close()
        setPhase({ kind: 'failed', error: job.error ?? 'El análisis ha fallado.' })
      } else {
        setPhase({ kind: 'running', done: job.done, total: job.total })
      }
    },
    [loadReview],
  )

  const follow = useCallback(() => {
    source.current?.close()
    const es = factory(analysisApi.streamUrl(gameId))
    source.current = es
    const handle = (event: MessageEvent<string>) => {
      if (alive.current) apply(JSON.parse(event.data) as AnalysisJob)
    }
    es.addEventListener('progress', handle)
    es.addEventListener('done', handle)
    es.addEventListener('failed', handle)
    es.onerror = () => {
      // The stream dropped: ask for the status once and follow again if still running.
      es.close()
      analysisApi
        .status(gameId)
        .then((job) => {
          if (!alive.current) return
          apply(job)
          if (job.status === 'running' || job.status === 'pending') {
            window.setTimeout(() => {
              followAgain.current()
            }, 1000)
          }
        })
        .catch((error: unknown) => {
          if (alive.current) setPhase({ kind: 'error', message: message(error) })
        })
    }
  }, [apply, factory, gameId])

  useEffect(() => {
    followAgain.current = follow
  }, [follow])

  useEffect(() => {
    alive.current = true
    analysisApi
      .status(gameId)
      .then((job) => {
        apply(job)
        if (job.status === 'running' || job.status === 'pending') follow()
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) setPhase({ kind: 'none' })
        else setPhase({ kind: 'error', message: message(error) })
      })
    return () => {
      alive.current = false
      source.current?.close()
    }
  }, [apply, follow, gameId])

  const start = useCallback(() => {
    setPhase({ kind: 'running', done: 0, total: 0 })
    analysisApi
      .start(gameId)
      .then((job) => {
        apply(job)
        if (job.status !== 'done' && job.status !== 'failed') follow()
      })
      .catch((error: unknown) => {
        setPhase({ kind: 'error', message: message(error) })
      })
  }, [apply, follow, gameId])

  return { phase, start }
}
