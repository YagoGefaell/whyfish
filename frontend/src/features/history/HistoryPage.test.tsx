import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { gameState } from '../../test/factories'
import { mockApi } from '../../test/fetchMock'
import { HistoryPage } from './HistoryPage'

const LICHESS = gameState({
  id: 11,
  source: 'imported',
  platform: 'lichess',
  time_class: 'blitz',
  white_name: 'Yago',
  black_name: 'Rival',
  white_elo: 1500,
  black_elo: 1600,
  played_at: '2026-11-20T18:00:00Z',
  external_url: 'https://lichess.org/abc',
  result: '1-0',
  status: 'finished',
  move_count: 40,
})
const IDLE = { running: false, older: false, accounts: [], finished_at: null }
const QUEUE = { enabled: true, paused: false, pending: 3, current_game_id: 11, failed: 0 }

function renderPage(path = '/games') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <HistoryPage />
    </MemoryRouter>,
  )
}

describe('HistoryPage', () => {
  it('lists synchronised games with origin, pace and ratings', async () => {
    mockApi([
      { path: '/api/games?limit=50&offset=0', body: { items: [LICHESS], total: 1 } },
      { path: '/api/sync', body: IDLE },
      { path: '/api/queue', body: QUEUE },
    ])
    renderPage()
    const row = (await screen.findByText('Yago (1500) – Rival (1600)')).closest('tr')
    if (!row) throw new Error('row')
    expect(row).toHaveTextContent('Lichess')
    expect(row).toHaveTextContent('Blitz')
    expect(within(row).getByRole('link', { name: 'Ver en Lichess' })).toHaveAttribute(
      'href',
      'https://lichess.org/abc',
    )
    expect(screen.getByRole('status', { name: 'Análisis automático' })).toHaveTextContent(
      '3 pendientes · analizando…',
    )
  })

  it('filters go to the request and the URL', async () => {
    const calls = mockApi([
      { path: '/api/games?result=win&limit=50&offset=0', body: { items: [LICHESS], total: 1 } },
      {
        path: '/api/games?platform=lichess&result=win&limit=50&offset=0',
        body: { items: [LICHESS], total: 1 },
      },
      { path: '/api/sync', body: IDLE },
      { path: '/api/queue', body: { ...QUEUE, pending: 0 } },
    ])
    renderPage('/games?result=win')
    await screen.findByText('Yago (1500) – Rival (1600)')
    fireEvent.change(screen.getByLabelText('Origen'), { target: { value: 'lichess' } })
    await waitFor(() => {
      expect(calls.map((c) => c.path)).toContain(
        '/api/games?platform=lichess&result=win&limit=50&offset=0',
      )
    })
  })

  it('pauses the queue and starts a sync', async () => {
    const calls = mockApi([
      { path: '/api/games?limit=50&offset=0', body: { items: [LICHESS], total: 1 } },
      { path: '/api/sync', body: IDLE },
      { path: '/api/queue', body: QUEUE },
      { method: 'POST', path: '/api/queue/pause', body: { ...QUEUE, paused: true } },
      {
        method: 'POST',
        path: '/api/sync',
        status: 400,
        body: { detail: 'Configura tus cuentas de Lichess o Chess.com en Ajustes.' },
      },
    ])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Pausar' }))
    await screen.findByRole('button', { name: 'Reanudar' })
    expect(screen.getByRole('status', { name: 'Análisis automático' })).toHaveTextContent(
      '(en pausa)',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Sincronizar' }))
    expect(await screen.findByRole('link', { name: 'Ir a Ajustes' })).toHaveAttribute(
      'href',
      '/settings',
    )
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/sync')).toBe(true)
  })
})
