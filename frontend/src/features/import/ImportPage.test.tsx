import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { gameState } from '../../test/factories'
import { mockApi } from '../../test/fetchMock'
import { ImportPage } from './ImportPage'

function renderImport() {
  render(
    <MemoryRouter initialEntries={['/import']}>
      <Routes>
        <Route path="/import" element={<ImportPage />} />
        <Route path="/review/:id" element={<p>Revisión abierta</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ImportPage', () => {
  it('asks for the color when it cannot be detected, then imports and analyses', async () => {
    const calls = mockApi([
      {
        method: 'POST',
        path: '/api/games/import',
        status: 422,
        body: {
          detail: {
            code: 'color_required',
            message: 'No se pudo deducir…',
            white: 'Morphy',
            black: 'Duke',
          },
        },
      },
      {
        method: 'POST',
        path: '/api/games/import',
        status: 201,
        body: { game: gameState({ id: 9 }), warnings: [] },
      },
      { method: 'POST', path: '/api/games/9/analysis', status: 202, body: {} },
    ])
    renderImport()
    fireEvent.change(screen.getByLabelText('Pega el PGN'), { target: { value: '1. e4 e5 *' } })
    fireEvent.click(screen.getByRole('button', { name: 'Importar y analizar' }))

    const question = await screen.findByRole('alertdialog', { name: '¿Quién eras tú?' })
    expect(question).toHaveTextContent('Blancas: Morphy')
    // The second attempt (with the color) succeeds.
    fireEvent.click(screen.getByRole('button', { name: 'Negras: Duke' }))
    expect(await screen.findByText('Revisión abierta')).toBeInTheDocument()
    expect(calls.filter((c) => c.path === '/api/games/import')).toHaveLength(2)
    expect(calls.filter((c) => c.path === '/api/games/import')[1]?.body).toEqual({
      pgn: '1. e4 e5 *',
      user_color: 'black',
    })
    expect(calls.some((c) => c.path === '/api/games/9/analysis')).toBe(true)
  })

  it('shows import errors', async () => {
    mockApi([
      {
        method: 'POST',
        path: '/api/games/import',
        status: 400,
        body: { detail: 'El PGN está vacío.' },
      },
    ])
    renderImport()
    fireEvent.change(screen.getByLabelText('Pega el PGN'), { target: { value: 'x' } })
    fireEvent.click(screen.getByLabelText('Blancas'))
    fireEvent.click(screen.getByRole('button', { name: 'Importar y analizar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('El PGN está vacío.')
  })
})
