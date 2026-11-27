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
  it('shows and saves the accounts', async () => {
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
    fireEvent.change(lichess, { target: { value: 'yago2' } })
    fireEvent.change(screen.getByLabelText('Usuario de Chess.com'), { target: { value: 'cc' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await screen.findByText('Cuentas guardadas.')
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      lichess: 'yago2',
      chesscom: 'cc',
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
