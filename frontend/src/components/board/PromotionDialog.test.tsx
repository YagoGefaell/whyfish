import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PromotionDialog } from './PromotionDialog'

describe('PromotionDialog', () => {
  it('returns the chosen piece', () => {
    const onSelect = vi.fn()
    render(<PromotionDialog color="white" onSelect={onSelect} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Caballo' }))
    expect(onSelect).toHaveBeenCalledWith('n')
  })

  it('can be cancelled', () => {
    const onCancel = vi.fn()
    render(<PromotionDialog color="black" onSelect={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onCancel).toHaveBeenCalled()
  })
})
