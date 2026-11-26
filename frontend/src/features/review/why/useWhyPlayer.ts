import { useCallback, useEffect, useState } from 'react'
import type { Why } from '../../../api/analysis'

/** Playback state of a "Ver por qué" sequence. index -1 = the position before the first move. */
export interface WhyPlayerState {
  index: number
  playing: boolean
  /** The end was reached by playing (the final card is shown while on the last step). */
  finished: boolean
}

export interface WhyPlayer extends WhyPlayerState {
  toggle: () => void
  next: () => void
  prev: () => void
  goTo: (index: number) => void
  restart: () => void
  /** On the last step after playing it through: show the final card. */
  atEnd: boolean
}

const START: WhyPlayerState = { index: -1, playing: true, finished: false }

/** Steps forward every `why.step_ms` while playing; stops on the last step. */
export function useWhyPlayer(why: Why | null): WhyPlayer {
  const [state, setState] = useState<{ why: Why | null; s: WhyPlayerState }>({ why, s: START })
  // A new sequence starts from the beginning (state derived from the prop, no effect needed).
  const current = state.why === why ? state.s : START
  const set = useCallback(
    (update: (s: WhyPlayerState) => WhyPlayerState) => {
      setState((prev) => ({ why, s: update(prev.why === why ? prev.s : START) }))
    },
    [why],
  )
  const last = why ? why.steps.length - 1 : -1

  useEffect(() => {
    if (!why || !current.playing) return
    const timer = window.setTimeout(() => {
      set((s) => {
        const index = Math.min(last, s.index + 1)
        return index >= last ? { index, playing: false, finished: true } : { ...s, index }
      })
    }, why.step_ms)
    return () => {
      window.clearTimeout(timer)
    }
  }, [why, current, last, set])

  const goTo = useCallback(
    (index: number) => {
      set((s) => ({
        index: Math.max(-1, Math.min(last, index)),
        playing: false,
        finished: s.finished || index >= last,
      }))
    },
    [set, last],
  )

  return {
    ...current,
    atEnd: current.finished && !current.playing && current.index === last && last >= 0,
    toggle: () => {
      if (current.index >= last) {
        set(() => ({ ...START }))
      } else {
        set((s) => ({ ...s, playing: !s.playing }))
      }
    },
    next: () => {
      goTo(current.index + 1)
    },
    prev: () => {
      goTo(current.index - 1)
    },
    goTo,
    restart: () => {
      set(() => ({ ...START }))
    },
  }
}
