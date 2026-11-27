import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { StatsResponse } from '../../api/stats'
import { mockApi } from '../../test/fetchMock'
import { StatsPage } from './StatsPage'

const EXAMPLE = {
  game_id: 7,
  ply: 41,
  san: 'dxc3',
  classification: 'blunder',
  delta: 40,
  date: '2026-11-20T10:00:00Z',
  opponent: 'rival',
}
const STATS: StatsResponse = {
  games_finished: 6,
  games_unanalysed: 2,
  insights_pending: 0,
  stats: {
    games: 4,
    enough: false,
    min_games: 10,
    accuracy_mean: 72.5,
    accuracy: [{ game_id: 7, date: '2026-11-20T10:00:00Z', accuracy: 72.5, average: 72.5 }],
    phases: [
      { phase: 'opening', label: 'Apertura', moves: 40, errors: 1, per10: 0.25, examples: [] },
      {
        phase: 'middlegame',
        label: 'Medio juego',
        moves: 60,
        errors: 3,
        per10: 0.5,
        examples: [EXAMPLE],
      },
      { phase: 'endgame', label: 'Final', moves: 0, errors: 0, per10: 0, examples: [] },
    ],
    kinds: [
      { kind: 'hanging', label: 'Pieza colgada', count: 3, mean_delta: 25, examples: [EXAMPLE] },
    ],
    openings: [
      {
        color: 'white',
        family: 'Italian Game',
        games: 3,
        wins: 0,
        draws: 1,
        losses: 2,
        score: 16.7,
        accuracy: 60,
        worst: true,
        game_ids: [7],
      },
    ],
    time: {
      games_with_clock: 4,
      low_moves: 20,
      low_errors: 6,
      normal_moves: 80,
      normal_errors: 4,
      low_rate: 0.3,
      normal_rate: 0.05,
      stands_out: true,
      examples: [EXAMPLE],
    },
    weak_points: [
      {
        key: 'hanging:middlegame',
        title: 'Dejas piezas sin defensa en el medio juego',
        text: '3 veces en 4 partidas.',
        advice: 'Antes de mover, comprueba qué piezas quedan sin defensa.',
        cost: 18.8,
        examples: [EXAMPLE],
        train: { error_kind: 'hanging', phase: 'middlegame' },
      },
    ],
  },
}

function renderAt(path = '/stats') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <StatsPage />
    </MemoryRouter>,
  )
}

describe('StatsPage', () => {
  it('says how many games count, warns when few, and links every figure to positions', async () => {
    mockApi([{ path: '/api/stats', body: STATS }])
    renderAt()
    const status = await screen.findByRole('status', { name: 'Partidas analizadas' })
    expect(status).toHaveTextContent('Basado en 4 partidas analizadas (solo partidas reales')
    expect(status).toHaveTextContent('2 más aún sin analizar')
    expect(status).toHaveTextContent('Son pocas para sacar conclusiones fiables (al menos 10)')
    expect(screen.getByText('1. Dejas piezas sin defensa en el medio juego')).toBeInTheDocument()
    const examples = screen.getByRole('list', {
      name: 'Ejemplos: Dejas piezas sin defensa en el medio juego',
    })
    expect(within(examples).getByRole('link')).toHaveAttribute('href', '/review/7?ply=41')
    expect(within(examples).getByRole('link')).toHaveTextContent('21…dxc3??')
    expect(
      screen.getByText('El reloj te está costando partidas.', { exact: false }),
    ).toBeInTheDocument()
    expect(screen.getByText('Italian Game').closest('tr')).toHaveAttribute('data-worst', 'true')
  })

  it('filters: real games by default, bot games and pace on demand', async () => {
    const calls = mockApi([
      { path: '/api/stats', body: STATS },
      { path: '/api/stats?include_bot=true', body: STATS },
      { path: '/api/stats?include_bot=true&time_class=blitz', body: STATS },
    ])
    renderAt()
    await screen.findByRole('status', { name: 'Partidas analizadas' })
    fireEvent.click(screen.getByLabelText('Incluir partidas contra el bot'))
    await waitFor(() => {
      expect(calls.map((c) => c.path)).toContain('/api/stats?include_bot=true')
    })
    fireEvent.change(screen.getByLabelText('Ritmo'), { target: { value: 'blitz' } })
    await waitFor(() => {
      expect(calls.map((c) => c.path)).toContain('/api/stats?include_bot=true&time_class=blitz')
    })
  })
})
