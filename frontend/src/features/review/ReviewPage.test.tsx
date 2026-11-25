import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../../test/fetchMock'
import { FOOLS_GAME, FOOLS_REVIEW } from '../../test/reviewFixture'
import { ReviewPage } from './ReviewPage'
import type { EventSourceLike } from './useAnalysis'

class FakeEventSource implements EventSourceLike {
  static last: FakeEventSource | null = null
  readonly url: string
  listeners = new Map<string, (e: MessageEvent<string>) => void>()
  onerror: ((event: Event) => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.last = this
  }

  addEventListener(type: string, listener: (e: MessageEvent<string>) => void) {
    this.listeners.set(type, listener)
  }

  emit(type: string, data: unknown) {
    this.listeners.get(type)?.(new MessageEvent(type, { data: JSON.stringify(data) }))
  }

  close() {
    this.closed = true
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/review/3']}>
      <Routes>
        <Route
          path="/review/:id"
          element={<ReviewPage eventSourceFactory={(url) => new FakeEventSource(url)} />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

const job = (status: string, done: number, total: number) => ({
  game_id: 3,
  status,
  done,
  total,
  error: null,
})

describe('ReviewPage', () => {
  it('follows the progress over SSE and then shows the review', async () => {
    mockApi([
      { path: '/api/games/3', body: FOOLS_GAME },
      { path: '/api/games/3/analysis', body: job('running', 1, 4) },
      { path: '/api/games/3/review', body: FOOLS_REVIEW },
    ])
    renderPage()
    const bar = await screen.findByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '25')
    expect(FakeEventSource.last?.url).toBe('/api/games/3/analysis/stream')

    act(() => {
      FakeEventSource.last?.emit('progress', job('running', 3, 4))
    })
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '75')

    act(() => {
      FakeEventSource.last?.emit('done', job('done', 4, 4))
    })
    expect(await screen.findByRole('table', { name: 'Resumen' })).toBeInTheDocument()
    expect(FakeEventSource.last?.closed).toBe(true)
  })

  it('offers to analyse a game that was never analysed', async () => {
    const calls = mockApi([
      { path: '/api/games/3', body: { ...FOOLS_GAME, analysis_status: null } },
      {
        path: '/api/games/3/analysis',
        status: 404,
        body: { detail: 'La partida no se ha analizado.' },
      },
      { method: 'POST', path: '/api/games/3/analysis', status: 202, body: job('pending', 0, 0) },
    ])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Analizar partida' }))
    expect(await screen.findByRole('progressbar')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/games/3/analysis')).toBe(true)
  })

  it('shows a failed analysis with a retry button', async () => {
    mockApi([
      { path: '/api/games/3', body: FOOLS_GAME },
      { path: '/api/games/3/analysis', body: { ...job('failed', 1, 4), error: 'Motor caído' } },
    ])
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Motor caído')
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
  })
})
