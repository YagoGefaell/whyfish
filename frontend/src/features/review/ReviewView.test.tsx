import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi } from '../../test/fetchMock'
import { FOOLS_GAME, FOOLS_REVIEW } from '../../test/reviewFixture'
import { ReviewView } from './ReviewView'

function renderReview() {
  return render(
    <MemoryRouter>
      <ReviewView game={FOOLS_GAME} review={FOOLS_REVIEW} />
    </MemoryRouter>,
  )
}

const panel = () => screen.getByRole('region', { name: 'Panel de revisión' })
const verdict = () => within(panel()).getAllByRole('heading')[0]
const banner = () => screen.queryByRole('status', { name: 'Variante explorada' })
const press = (key: string) => {
  fireEvent.keyDown(window, { key })
}
const startReview = () => {
  fireEvent.click(screen.getByRole('button', { name: 'Empezar revisión' }))
}

describe('ReviewView', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('opens on the summary, with the user column highlighted', () => {
    renderReview()
    expect(screen.getByRole('tab', { name: 'Resumen' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('accuracy-white')).toHaveTextContent('41.2')
    expect(screen.getByTestId('accuracy-white').className).toContain('ring-1') // the user (white)
    expect(screen.getByTestId('accuracy-black').className).not.toContain('ring-1')
    expect(screen.getByRole('table', { name: 'Resumen' })).toBeInTheDocument()
  })

  it('"Empezar revisión" goes to move 1 with a coach sentence', () => {
    renderReview()
    startReview()
    expect(screen.getByRole('tab', { name: 'Revisión' })).toHaveAttribute('aria-selected', 'true')
    expect(verdict()).toHaveTextContent('f3 es una imprecisión')
    expect(within(panel()).getByLabelText('Explicación')).toHaveTextContent('«imprecisión»')
  })

  it('navigates with the arrow keys, Home and End', () => {
    renderReview()
    startReview()
    press('ArrowRight')
    expect(verdict()).toHaveTextContent('e5 es la mejor jugada')
    press('ArrowRight')
    expect(verdict()).toHaveTextContent('g4 es un grave error')
    press('ArrowLeft')
    expect(verdict()).toHaveTextContent('e5')
    press('End')
    expect(verdict()).toHaveTextContent('Qh4#')
    press('ArrowRight') // already at the end
    expect(verdict()).toHaveTextContent('Qh4#')
    press('Home')
    expect(verdict()).toHaveTextContent('Posición inicial')
  })

  it('jumps to the next error of the user with N and the button', () => {
    renderReview()
    press('n')
    expect(verdict()).toHaveTextContent('f3 es una imprecisión')
    fireEvent.click(within(panel()).getByRole('button', { name: /Siguiente error/ }))
    expect(verdict()).toHaveTextContent('g4 es un grave error')
    // No more errors of white after g4 (Qh4# is black's).
    expect(within(panel()).getByRole('button', { name: /Siguiente error/ })).toBeDisabled()
  })

  it('ignores the keys while typing in a field', () => {
    render(
      <MemoryRouter>
        <input aria-label="campo" />
        <ReviewView game={FOOLS_GAME} review={FOOLS_REVIEW} />
      </MemoryRouter>,
    )
    fireEvent.keyDown(screen.getByLabelText('campo'), { key: 'n' })
    expect(screen.getByRole('tab', { name: 'Resumen' })).toHaveAttribute('aria-selected', 'true')
  })

  it('jumps from the evaluation graph and from the key moments', () => {
    renderReview()
    const moments = screen.getByRole('list', { name: 'Momentos clave' })
    fireEvent.click(within(moments).getByRole('button', { name: /1\. f3/ }))
    expect(verdict()).toHaveTextContent('f3')
    fireEvent.click(screen.getByRole('button', { name: 'Ir a 2. g4' }))
    expect(verdict()).toHaveTextContent('g4')
  })

  it('puts the badge on the destination square', () => {
    renderReview()
    fireEvent.click(screen.getByRole('button', { name: 'Ir a 2. g4' }))
    const badge = screen.getByTestId('move-badge')
    expect(within(badge).getByRole('img', { name: 'Grave error' })).toBeInTheDocument()
    expect(badge.closest('[data-square]')).toHaveAttribute('data-square', 'g4')
  })

  it('shows badges in the list only for !!, !, ?!, ?, ?? and ✗', () => {
    renderReview()
    startReview()
    const list = screen.getByRole('list', { name: 'Jugadas' })
    const f3 = within(list).getByRole('button', { name: /f3/ })
    const e5 = within(list).getByRole('button', { name: /e5/ })
    expect(within(f3).getByRole('img', { name: 'Imprecisión' })).toBeInTheDocument()
    expect(within(e5).queryByRole('img')).toBeNull() // "best": no badge in the list
  })

  it('shows the best move automatically when the move was not the best', () => {
    renderReview()
    startReview()
    press('ArrowRight') // e5: best -> no alternative
    expect(within(panel()).queryByText(/La mejor era/)).toBeNull()
    expect(within(panel()).queryByRole('button', { name: 'Ver línea' })).toBeNull()
    press('ArrowLeft') // f3: inaccuracy -> "La mejor era e4", line on demand
    expect(within(panel()).getByText(/La mejor era/)).toHaveTextContent('La mejor era e4')
    expect(within(panel()).queryByLabelText('Línea de la mejor jugada')).toBeNull()
    fireEvent.click(within(panel()).getByRole('button', { name: 'Ver línea' }))
    // Numbered from the move it replaces (1. f3 -> "1. e4 e5 2. Nf3"), moves still clickable.
    const line = within(panel()).getByLabelText('Línea de la mejor jugada')
    expect(line).toHaveTextContent(/^1\.\s*e4\s*e5\s*2\.\s*Nf3$/)
    expect(
      within(line)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['e4', 'e5', 'Nf3'])
    expect(verdict()).toHaveTextContent('1. f3 es una imprecisión')
  })

  it('shows the final position on the summary and the user at the bottom', () => {
    renderReview()
    // Final position of the fool's mate: black queen on h4.
    expect(document.querySelector('[data-square="h4"] [data-piece-image="bQ"]')).not.toBeNull()
    expect(screen.getByTestId('player-bottom')).toHaveTextContent('Tú')
    expect(screen.getByTestId('player-top')).toHaveTextContent('Stockfish')
    expect(screen.getByTestId('player-bottom-accuracy')).toHaveTextContent('41.2')
    expect(screen.getByTestId('player-top-accuracy')).toHaveTextContent('100.0')
  })

  it('remembers whether the engine details are open', () => {
    const { unmount } = renderReview()
    startReview()
    const details = () => within(panel()).getByText('Detalles del motor').closest('details')
    expect(details()).not.toHaveAttribute('open')
    fireEvent.click(within(panel()).getByText('Detalles del motor'))
    details()?.dispatchEvent(new Event('toggle'))
    expect(window.localStorage.getItem('whyfish.review.engineDetails')).toBe('1')
    unmount()
    renderReview()
    startReview()
    expect(details()).toHaveAttribute('open')
  })

  it('explores a line with the engine evaluation and returns to the game', async () => {
    const calls = mockApi([
      {
        method: 'POST',
        path: '/api/analysis/evaluate',
        body: {
          fen: 'x',
          turn: 'white',
          terminal: null,
          lines: [{ uci: ['g1f3', 'b8c6'], san: ['Nf3', 'Nc6'], cp: 30, mate: null, win: 52.8 }],
          best_uci: 'g1f3',
          best_san: 'Nf3',
          white: { win: 52.8, cp: 30, mate: null },
        },
      },
    ])
    renderReview()
    startReview()
    fireEvent.click(within(panel()).getByRole('button', { name: 'Ver línea' }))
    const line = within(panel()).getByLabelText('Línea de la mejor jugada')
    fireEvent.click(within(line).getByRole('button', { name: 'e5' }))

    const variant = banner()
    expect(variant).toHaveTextContent('Variante desde la posición inicial')
    expect(
      await within(variant as HTMLElement).findByText(/Evaluación \+0\.3 · mejor línea: Nf3 Nc6/),
    ).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/analysis/evaluate')?.body).toEqual({
      fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      moves: ['e2e4', 'e7e5'],
    })

    press('Escape')
    expect(banner()).toBeNull()
    expect(verdict()).toHaveTextContent('Posición inicial')
  })

  it('debounces evaluations: moving fast sends only the last position', async () => {
    const calls = mockApi([
      {
        method: 'POST',
        path: '/api/analysis/evaluate',
        body: {
          fen: 'x',
          turn: 'black',
          terminal: null,
          lines: [],
          best_uci: null,
          best_san: null,
          white: { win: 50, cp: 0, mate: null },
        },
      },
    ])
    renderReview()
    startReview()
    fireEvent.click(within(panel()).getByRole('button', { name: 'Ver línea' }))
    const line = within(panel()).getByLabelText('Línea de la mejor jugada')
    fireEvent.click(within(line).getByRole('button', { name: 'Nf3' }))
    press('ArrowLeft')
    press('ArrowLeft') // three positions in a row, faster than the debounce
    await waitFor(() => {
      expect(calls.filter((c) => c.path === '/api/analysis/evaluate')).toHaveLength(1)
    })
    await act(() => new Promise((r) => setTimeout(r, 400)))
    const sent = calls.filter((c) => c.path === '/api/analysis/evaluate')
    expect(sent).toHaveLength(1)
    expect(sent[0]?.body).toMatchObject({ moves: ['e2e4'] })
  })
})
