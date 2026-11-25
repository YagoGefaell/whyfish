import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
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

const detail = () => screen.getByRole('region', { name: 'Detalle de la jugada' })
const heading = () => within(detail()).getAllByRole('heading')[0]
const banner = () => screen.queryByRole('status', { name: 'Variante explorada' })
const press = (key: string) => {
  fireEvent.keyDown(window, { key })
}

describe('ReviewView', () => {
  it('starts at the initial position and shows the summary', () => {
    renderReview()
    expect(within(detail()).getByText(/Posición inicial/)).toBeInTheDocument()
    const summary = screen.getByRole('table', { name: 'Resumen' })
    expect(within(summary).getByText('41.2')).toBeInTheDocument()
    expect(screen.getByText('Barnes Opening')).toBeInTheDocument()
  })

  it('navigates with the arrow keys, Home and End', () => {
    renderReview()
    press('ArrowRight')
    expect(heading()).toHaveTextContent('1. f3 · Imprecisión')
    press('ArrowRight')
    press('ArrowRight')
    expect(heading()).toHaveTextContent('2. g4 · Grave error')
    press('ArrowLeft')
    expect(heading()).toHaveTextContent('1… e5')
    press('End')
    expect(heading()).toHaveTextContent('2… Qh4#')
    press('ArrowRight') // already at the end
    expect(heading()).toHaveTextContent('2… Qh4#')
    press('Home')
    expect(within(detail()).getByText(/Posición inicial/)).toBeInTheDocument()
  })

  it('ignores the keys while typing in a field', () => {
    render(
      <MemoryRouter>
        <input aria-label="campo" />
        <ReviewView game={FOOLS_GAME} review={FOOLS_REVIEW} />
      </MemoryRouter>,
    )
    fireEvent.keyDown(screen.getByLabelText('campo'), { key: 'ArrowRight' })
    expect(within(detail()).getByText(/Posición inicial/)).toBeInTheDocument()
  })

  it('jumps to a move from the evaluation graph and from the key moments', () => {
    renderReview()
    fireEvent.click(screen.getByRole('button', { name: 'Ir a 2. g4' }))
    expect(heading()).toHaveTextContent('2. g4')
    const moments = screen.getByRole('list', { name: 'Momentos clave' })
    fireEvent.click(within(moments).getByRole('button', { name: /1\. f3/ }))
    expect(heading()).toHaveTextContent('1. f3')
  })

  it('puts the classification badge on the destination square', () => {
    renderReview()
    press('ArrowRight')
    press('ArrowRight')
    press('ArrowRight')
    const badge = screen.getByTestId('move-badge')
    expect(badge).toHaveTextContent('??')
    expect(badge.closest('[data-square]')).toHaveAttribute('data-square', 'g4')
  })

  it('shows the best move and a placeholder explanation', () => {
    renderReview()
    press('ArrowRight')
    expect(within(detail()).getByText(/Mejor era/)).toHaveTextContent('Mejor era e4')
    expect(within(detail()).getByRole('region', { name: 'Explicación' })).toHaveTextContent(
      'por qué esta jugada es «Imprecisión»',
    )
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
    press('ArrowRight')
    const line = screen.getByLabelText('Línea de la mejor jugada')
    fireEvent.click(within(line).getByRole('button', { name: 'e5' }))

    const variant = banner()
    expect(variant).toHaveTextContent('Explorando una variante desde la posición inicial')
    expect(
      await within(variant as HTMLElement).findByText(/Evaluación \+0\.3 · mejor línea: Nf3 Nc6/),
    ).toBeInTheDocument()
    const request = calls.find((c) => c.path === '/api/analysis/evaluate')
    expect(request?.body).toEqual({
      fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      moves: ['e2e4', 'e7e5'],
    })

    press('Escape')
    expect(banner()).toBeNull()
    expect(within(detail()).getByText(/Posición inicial/)).toBeInTheDocument()
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
    press('ArrowRight')
    const line = screen.getByLabelText('Línea de la mejor jugada')
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
