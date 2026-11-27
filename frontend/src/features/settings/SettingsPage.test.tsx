import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../../test/fetchMock'
import { SettingsPage } from './SettingsPage'

const ACCOUNTS = {
  sync_months: 6,
  accounts: [
    {
      platform: 'lichess',
      username: 'Yago',
      covered_from: '2026-05-27T00:00:00Z',
      newest_at: '2026-11-26T10:00:00Z',
      last_synced_at: '2026-11-27T09:00:00Z',
      last_error: null,
      imported_count: 42,
    },
  ],
}
const IDLE = { running: false, older: false, accounts: [], finished_at: null }

function renderPage() {
  render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

describe('SettingsPage', () => {
  it('saves the accounts on leaving the field, only when they changed', async () => {
    const calls = mockApi([
      { path: '/api/accounts', body: ACCOUNTS },
      { path: '/api/sync', body: IDLE },
      {
        method: 'PUT',
        path: '/api/accounts',
        body: { ...ACCOUNTS, accounts: [{ ...ACCOUNTS.accounts[0], username: 'yago2' }] },
      },
    ])
    renderPage()
    const lichess = await screen.findByLabelText('Usuario de Lichess')
    expect(lichess).toHaveValue('Yago')
    expect(screen.getByTestId('account-lichess')).toHaveTextContent('42 importadas')
    expect(screen.queryByRole('button', { name: 'Guardar' })).toBeNull()
    // Leaving a field without changes saves nothing.
    fireEvent.blur(lichess)
    fireEvent.change(lichess, { target: { value: 'yago2' } })
    const chesscom = screen.getByLabelText('Usuario de Chess.com')
    fireEvent.change(chesscom, { target: { value: 'cc' } })
    fireEvent.blur(chesscom)
    await screen.findByText('Guardado')
    const puts = calls.filter((c) => c.method === 'PUT')
    expect(puts).toHaveLength(1)
    expect(puts[0]?.body).toEqual({ lichess: 'yago2', chesscom: 'cc' })
  })

  it('saves the training settings when they change', async () => {
    const TRAINING = { session_size: 5, weak_new: 3, include_bullet: false, include_bot: true }
    const calls = mockApi([
      { path: '/api/accounts', body: ACCOUNTS },
      { path: '/api/sync', body: IDLE },
      { path: '/api/training/settings', body: TRAINING },
      {
        method: 'PUT',
        path: '/api/training/settings',
        body: { ...TRAINING, include_bullet: true },
      },
    ])
    renderPage()
    fireEvent.click(await screen.findByLabelText('Incluir errores de partidas bala'))
    const section = await screen.findByRole('region', { name: 'Entrenamiento' })
    await waitFor(() => {
      expect(section).toHaveTextContent('Guardado')
    })
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      ...TRAINING,
      include_bullet: true,
    })
  })

  it('imports older games', async () => {
    const calls = mockApi([
      { path: '/api/accounts', body: ACCOUNTS },
      { path: '/api/sync', body: IDLE },
      {
        method: 'POST',
        path: '/api/sync',
        body: {
          running: true,
          older: true,
          finished_at: null,
          accounts: [
            {
              platform: 'lichess',
              username: 'Yago',
              state: 'running',
              imported: 3,
              skipped: 0,
              error: null,
            },
          ],
        },
      },
    ])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Importar partidas más antiguas' }))
    await waitFor(() => {
      expect(screen.getByRole('list', { name: 'Sincronización' })).toHaveTextContent(
        'Lichess (Yago): importando… · 3 nuevas',
      )
    })
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ older: true })
  })
})
