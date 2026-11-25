import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { gameState } from '../../test/factories'
import { mockApi } from '../../test/fetchMock'
import { PlayPage } from './PlayPage'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/play/:id" element={<PlayPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const MID_GAME = gameState({
  fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 2 3',
  moves: [
    { ply: 0, uci: 'e2e4', san: 'e4', by_bot: false },
    { ply: 1, uci: 'e7e5', san: 'e5', by_bot: true },
    { ply: 2, uci: 'f1c4', san: 'Bc4', by_bot: false },
    { ply: 3, uci: 'b8c6', san: 'Nc6', by_bot: true },
  ],
  move_count: 4,
  allow_undo: true,
  allow_hint: true,
  undo_count: 1,
  hint_count: 2,
})

describe('PlayPage', () => {
  it('restores a game in progress from the server on reload', async () => {
    mockApi([{ path: '/api/games/7', body: MID_GAME }])
    renderAt('/play/7')

    expect(await screen.findByText('Te toca (blancas)')).toBeInTheDocument()
    const moves = screen.getByRole('list', { name: 'Jugadas' })
    expect(
      within(moves)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['1.e4e5', '2.Bc4Nc6'])
    expect(screen.getByText(/Ayudas usadas: deshacer 1 · pistas 2/)).toBeInTheDocument()
    // Position from the server's FEN: white bishop on c4, black knight on c6.
    expect(document.querySelector('[data-square="c4"] [data-piece="wB"]')).not.toBeNull()
    expect(document.querySelector('[data-square="c6"] [data-piece="bN"]')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Deshacer' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Pista' })).toBeEnabled()
  })

  it('hides assists that were not enabled', async () => {
    mockApi([{ path: '/api/games/7', body: gameState() }])
    renderAt('/play/7')
    await screen.findByText('Te toca (blancas)')
    expect(screen.queryByRole('button', { name: 'Deshacer' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Pista' })).toBeNull()
  })

  it('shows the result of a finished game', async () => {
    mockApi([
      {
        path: '/api/games/7',
        body: gameState({ status: 'finished', result: '0-1', termination: 'checkmate' }),
      },
    ])
    renderAt('/play/7')
    expect(await screen.findByText('Has perdido por jaque mate')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Abandonar' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Descargar PGN' })).toHaveAttribute(
      'href',
      '/api/games/7/pgn',
    )
  })

  it('resigns after confirmation', async () => {
    const calls = mockApi([
      { path: '/api/games/7', body: gameState() },
      {
        method: 'POST',
        path: '/api/games/7/resign',
        body: gameState({ status: 'finished', result: '0-1', termination: 'resignation' }),
      },
    ])
    renderAt('/play/7')
    fireEvent.click(await screen.findByRole('button', { name: 'Abandonar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sí, abandonar' }))
    expect(await screen.findByText('Has perdido por abandono')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/games/7/resign')).toBe(true)
  })

  it('reports a declined draw offer', async () => {
    mockApi([
      { path: '/api/games/7', body: gameState() },
      {
        method: 'POST',
        path: '/api/games/7/draw',
        body: { accepted: false, declined_reason: 'position', min_moves: 20, game: gameState() },
      },
    ])
    renderAt('/play/7')
    fireEvent.click(await screen.findByRole('button', { name: 'Ofrecer tablas' }))
    expect(await screen.findByText('Stockfish rechaza las tablas.')).toBeInTheDocument()
  })

  it('explains a draw offer declined because it is too early', async () => {
    mockApi([
      { path: '/api/games/7', body: gameState() },
      {
        method: 'POST',
        path: '/api/games/7/draw',
        body: {
          accepted: false,
          declined_reason: 'too_early',
          min_moves: 20,
          game: gameState(),
        },
      },
    ])
    renderAt('/play/7')
    fireEvent.click(await screen.findByRole('button', { name: 'Ofrecer tablas' }))
    expect(
      await screen.findByText('Stockfish no acepta tablas hasta que se hayan jugado 20 jugadas.'),
    ).toBeInTheDocument()
  })

  it('shows a load error for a missing game', async () => {
    mockApi([{ path: '/api/games/99', status: 404, body: { detail: 'Partida no encontrada.' } }])
    renderAt('/play/99')
    await waitFor(() => {
      expect(screen.getByText('Partida no encontrada.')).toBeInTheDocument()
    })
  })
})
