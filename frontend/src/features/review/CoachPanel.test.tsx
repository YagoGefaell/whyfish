import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { MoveReview } from '../../api/analysis'
import { FOOLS_REVIEW } from '../../test/reviewFixture'
import { CoachPanel } from './CoachPanel'

function renderPanel(move: MoveReview, onLine = vi.fn()) {
  render(
    <CoachPanel
      move={move}
      evalAfter={null}
      onLine={onLine}
      explanation={null}
      explanationLoading={false}
      deep={false}
      onDeep={vi.fn()}
      onRef={vi.fn()}
      onWhy={vi.fn()}
      onTry={vi.fn()}
      whyLoading={false}
      whyError={null}
    />,
  )
  return onLine
}

describe('CoachPanel: moves as good as the best', () => {
  it('not the best: "La mejor era X (o Y, igual de buena)"', () => {
    const f3 = FOOLS_REVIEW.moves[0]
    const onLine = renderPanel({ ...f3, equal_best_uci: ['d2d4'], equal_best_san: ['d4'] })
    expect(screen.getByLabelText('Mejor jugada')).toHaveTextContent(
      /La mejor era e4\s*\(o d4, igual de buena\)/,
    )
    fireEvent.click(screen.getByRole('button', { name: 'd4' }))
    expect(onLine).toHaveBeenCalledWith('before', ['d4'], 0)
  })

  it('a best move: "También valía Y"', () => {
    const e5 = FOOLS_REVIEW.moves[1]
    renderPanel({ ...e5, equal_best_uci: ['b8c6', 'g8f6'], equal_best_san: ['Nc6', 'Nf6'] })
    expect(screen.getByLabelText('Igual de buenas')).toHaveTextContent('También valía Nc6 o Nf6.')
  })

  it('a move as good as the stored best names the stored best', () => {
    const e5 = FOOLS_REVIEW.moves[1]
    renderPanel({ ...e5, best_uci: 'b8c6', best_san: 'Nc6' })
    expect(screen.getByLabelText('Igual de buenas')).toHaveTextContent('También valía Nc6.')
  })
})
