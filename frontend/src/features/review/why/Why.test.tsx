import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import type { TryResult, Why } from '../../../api/analysis'
import { mockApi } from '../../../test/fetchMock'
import { FOOLS_GAME, FOOLS_REVIEW } from '../../../test/reviewFixture'
import { ReviewView } from '../ReviewView'
import { TryIt } from './TryIt'

const AFTER_F3_E5 = 'rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2'

const WHY: Why = {
  kind: 'refutation',
  tone: 'bad',
  base_ply: 2,
  start_fen: AFTER_F3_E5,
  title: 'Por qué 2.g4 es un error grave',
  alternative: null,
  steps: [
    {
      index: 0,
      label: '2.g4',
      san: 'g4',
      uci: 'g2g4',
      fen: 'rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2',
      color: 'white',
      caption: 'Tu peón va a g4',
      defense: false,
      consequence: false,
      arrows: [],
    },
    {
      index: 1,
      label: '2…Qh4#',
      san: 'Qh4#',
      uci: 'd8h4',
      fen: 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3',
      color: 'black',
      caption: 'La dama rival da jaque mate',
      defense: false,
      consequence: true,
      arrows: [],
    },
  ],
  consequence_ply: 1,
  summary: 'Esta jugada permite mate inmediato. Mejor era [[e3]].',
  refs: [{ san: 'e3', line: 'best', base: 2, path: ['e2e3'] }],
  step_ms: 20,
}

function renderAtG4() {
  render(
    <MemoryRouter>
      <ReviewView game={FOOLS_GAME} review={FOOLS_REVIEW} />
    </MemoryRouter>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Empezar revisión' }))
  fireEvent.keyDown(window, { key: 'ArrowRight' })
  fireEvent.keyDown(window, { key: 'ArrowRight' })
}
const panel = () => screen.getByRole('region', { name: 'Panel de revisión' })

describe('Ver por qué', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('replays the sequence up to the consequence and shows the result', async () => {
    mockApi([{ path: '/api/games/3/moves/2/why?kind=refutation', body: WHY }])
    renderAtG4()
    fireEvent.click(within(panel()).getByRole('button', { name: 'Ver por qué' }))
    const replay = await screen.findByRole('region', { name: 'Ver por qué' })
    expect(within(replay).getByRole('heading')).toHaveTextContent('Por qué 2.g4 es un error grave')
    // It plays by itself up to the last step, then shows the final card.
    const results = await screen.findAllByRole('status', { name: 'Resultado' })
    expect(results[0]).toHaveTextContent('Esta jugada permite mate inmediato.')
    // The consequence square is marked on the board.
    expect(document.getElementById('review-board-square-h4')?.innerHTML).toContain('inset')
    // ◀ goes back one step (the card disappears), Esc leaves the replay.
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    await waitFor(() => {
      expect(screen.queryAllByRole('status', { name: 'Resultado' })).toHaveLength(0)
    })
    expect(screen.getAllByLabelText('Paso actual')[0]).toHaveTextContent('Tu peón va a g4')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('region', { name: 'Ver por qué' })).toBeNull()
    expect(within(panel()).getByRole('button', { name: 'Ver por qué' })).toBeInTheDocument()
  })

  it('the sequence is clickable and marks the consequence', async () => {
    mockApi([{ path: '/api/games/3/moves/2/why?kind=refutation', body: WHY }])
    renderAtG4()
    fireEvent.click(within(panel()).getByRole('button', { name: 'Ver por qué' }))
    const sequence = await screen.findByRole('list', { name: 'Secuencia' })
    const mate = within(sequence).getByRole('button', { name: 'Qh4#' })
    expect(mate).toHaveAttribute('data-consequence', 'true')
    fireEvent.click(within(sequence).getByRole('button', { name: 'g4' }))
    expect(within(sequence).getByRole('button', { name: 'g4' })).toHaveAttribute(
      'aria-current',
      'step',
    )
  })

  it('"Pruébalo tú" hides the best move and can be left with Esc', () => {
    renderAtG4()
    fireEvent.click(within(panel()).getByRole('button', { name: 'Pruébalo tú' }))
    expect(screen.getByRole('region', { name: 'Pruébalo tú' })).toHaveTextContent(
      'Busca la mejor jugada para las blancas',
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('region', { name: 'Pruébalo tú' })).toBeNull()
  })
})

describe('TryIt', () => {
  const failed: TryResult = {
    uci: 'g2g4',
    san: 'g4',
    classification: 'blunder',
    correct: false,
    why: WHY,
  }
  const noop = () => undefined

  it('offers to retry, see why the attempt fails, or see the solution', () => {
    render(
      <TryIt
        state={{ status: 'done', result: failed }}
        side="white"
        busy={false}
        onRetry={noop}
        onWhyAttempt={noop}
        onSolution={noop}
        onExit={noop}
      />,
    )
    const options = screen.getByRole('group', { name: 'Opciones' })
    expect(
      within(options)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual([' Intentar otra vez', ' Ver por qué falla tu intento', ' Ver la solución'])
  })

  it('congratulates a correct move', () => {
    render(
      <TryIt
        state={{ status: 'done', result: { ...failed, san: 'e3', correct: true, why: null } }}
        side="white"
        busy={false}
        onRetry={noop}
        onWhyAttempt={noop}
        onSolution={noop}
        onExit={noop}
      />,
    )
    expect(screen.getByText(/¡Bien visto!/)).toHaveTextContent('e3 es la mejor jugada')
  })
})
