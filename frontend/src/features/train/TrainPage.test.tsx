import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { Exercise, TrainingSession } from '../../api/training'
import { mockApi } from '../../test/fetchMock'
import { TrainPage } from './TrainPage'

const COUNTS = { due: 0, new: 4, learned: 1, decided: 2, unclear: 3, bullet: 1 }
const SESSION: TrainingSession = {
  id: 9,
  daily: true,
  filter: {},
  positions: [
    { position: 0, item_id: 31, state: 'correct', repeat: false },
    { position: 1, item_id: 32, state: 'pending', repeat: false },
  ],
  current: 1,
  correct: 1,
  answered: 1,
  completed: false,
  streak: 3,
  counts: COUNTS,
}
const MISS: Exercise = {
  id: 32,
  kind: 'miss',
  prompt: 'El rival acaba de cometer un error: ¿cómo lo aprovechas?',
  fen: 'rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2',
  last_move: 'g2g4',
  context: {
    opponent: 'rival3 (1450)',
    origin: 'Chess.com',
    pace: 'rápida',
    move_number: 2,
    color: 'black',
  },
  error_kind: 'missed_mate',
  phase: 'opening',
  low_time: false,
}

function renderAt(path = '/train') {
  render(
    <MemoryRouter initialEntries={[path]}>
      <TrainPage />
    </MemoryRouter>,
  )
}

describe('TrainPage', () => {
  it('shows progress, streak and the exercise context without the solution', async () => {
    mockApi([
      { path: '/api/training/session', body: SESSION },
      { path: '/api/training/items/32', body: MISS },
    ])
    renderAt()
    expect(await screen.findByText(MISS.prompt)).toBeInTheDocument()
    expect(screen.getByTestId('exercise-context')).toHaveTextContent(
      'Partida contra rival3 (1450) (Chess.com, rápida), jugada 2, juegas con negras.',
    )
    expect(screen.getByTestId('to-move')).toHaveTextContent('Juegan las negras (tú)')
    expect(screen.getByLabelText('Progreso')).toHaveTextContent('2 / 2 · 1 aciertos')
    expect(screen.getByLabelText('Racha')).toHaveTextContent('Racha: 3 días')
    // The opponent's error is highlighted on the board; no link to the game before solving.
    expect(document.getElementById('review-board-square-g4')?.getAttribute('style') ?? '').not.toBe(
      '',
    )
    expect(screen.queryByText('Partida original')).toBeNull()
  })

  it('a filtered session says what it trains; an empty one explains why', async () => {
    mockApi([
      {
        path: '/api/training/session?error_kind=hanging&phase=middlegame',
        body: {
          ...SESSION,
          daily: false,
          filter: { error_kind: 'hanging', phase: 'middlegame' },
          positions: [],
          current: null,
          correct: 0,
          answered: 0,
          completed: true,
        },
      },
    ])
    renderAt('/train?error_kind=hanging&phase=middlegame')
    expect(await screen.findByText('Entrenando: Pieza colgada · medio juego')).toBeInTheDocument()
    expect(screen.getByText('No hay ejercicios de este tipo pendientes.')).toBeInTheDocument()
    expect(
      screen.getByText(/2 con la partida ya decidida, 3 sin una solución clara, 1 de bala/),
    ).toBeInTheDocument()
  })
})
