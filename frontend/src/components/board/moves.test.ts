import { describe, expect, it } from 'vitest'
import { applyUci, checkedKingSquare, resolveDrop } from './moves'

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const PROMO = '8/P6k/8/8/8/8/8/K7 w - - 0 1'

describe('resolveDrop', () => {
  it('accepts a legal move', () => {
    expect(resolveDrop(START, 'e2', 'e4')).toEqual({ kind: 'move', uci: 'e2e4' })
  })

  it('rejects illegal moves, drops off the board and drops on the same square', () => {
    expect(resolveDrop(START, 'e2', 'e5')).toEqual({ kind: 'illegal' })
    expect(resolveDrop(START, 'e2', null)).toEqual({ kind: 'illegal' })
    expect(resolveDrop(START, 'e2', 'e2')).toEqual({ kind: 'illegal' })
  })

  it('detects promotions', () => {
    expect(resolveDrop(PROMO, 'a7', 'a8')).toEqual({ kind: 'promotion', from: 'a7', to: 'a8' })
  })

  it('handles castling as a king move', () => {
    const fen = 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
    expect(resolveDrop(fen, 'e1', 'g1')).toEqual({ kind: 'move', uci: 'e1g1' })
  })
})

describe('applyUci', () => {
  it('returns the new FEN', () => {
    expect(applyUci(START, 'e2e4')).toMatch(/^rnbqkbnr\/pppppppp\/8\/8\/4P3\//)
  })

  it('applies promotions', () => {
    expect(applyUci(PROMO, 'a7a8n')?.startsWith('N7/7k/')).toBe(true)
  })

  it('returns null for illegal moves', () => {
    expect(applyUci(START, 'e2e5')).toBeNull()
  })
})

describe('checkedKingSquare', () => {
  it('finds the checked king', () => {
    const mated = 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3'
    expect(checkedKingSquare(mated)).toBe('e1')
  })

  it('returns null when not in check', () => {
    expect(checkedKingSquare(START)).toBeNull()
  })
})
