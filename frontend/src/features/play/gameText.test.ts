import { describe, expect, it } from 'vitest'
import { endText, moveRows, outcomeShortText, playerOutcome } from './gameText'

describe('playerOutcome', () => {
  it('maps results to the player point of view', () => {
    expect(playerOutcome('1-0', 'white')).toBe('win')
    expect(playerOutcome('1-0', 'black')).toBe('loss')
    expect(playerOutcome('0-1', 'black')).toBe('win')
    expect(playerOutcome('1/2-1/2', 'white')).toBe('draw')
  })
})

describe('texts', () => {
  it('describes the end of the game', () => {
    expect(endText('0-1', 'checkmate', 'white')).toBe('Has perdido por jaque mate')
    expect(endText('1/2-1/2', 'threefold_repetition', 'black')).toBe('Tablas por triple repetición')
  })

  it('short outcome for the history', () => {
    expect(outcomeShortText(null, 'white')).toBe('En curso')
    expect(outcomeShortText('1-0', 'white')).toBe('Has ganado')
  })
})

describe('moveRows', () => {
  it('numbers full moves', () => {
    expect(moveRows(['e4', 'e5', 'Nf3'])).toEqual([
      [1, 'e4', 'e5'],
      [2, 'Nf3', ''],
    ])
  })
})
