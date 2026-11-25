import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { gameState } from '../../test/factories'
import { mockApi } from '../../test/fetchMock'
import { NewGamePage } from './NewGamePage'

describe('NewGamePage', () => {
  it('creates a game with the chosen options and opens it', async () => {
    const calls = mockApi([
      {
        path: '/api/levels',
        body: [
          { id: 'beginner', label: 'Principiante ~800' },
          { id: 'club', label: 'Club ~1500' },
        ],
      },
      { method: 'POST', path: '/api/games', status: 201, body: gameState({ id: 42 }) },
    ])
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<NewGamePage />} />
          <Route path="/play/:id" element={<p>Partida abierta</p>} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByRole('option', { name: 'Principiante ~800' })
    fireEvent.click(screen.getByLabelText('Negras'))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'beginner' } })
    fireEvent.click(screen.getByLabelText('Permitir pistas (muestra qué pieza mover)'))
    fireEvent.click(screen.getByRole('button', { name: 'Empezar' }))

    expect(await screen.findByText('Partida abierta')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      color: 'black',
      level: 'beginner',
      allow_undo: false,
      allow_hint: true,
    })
  })
})
