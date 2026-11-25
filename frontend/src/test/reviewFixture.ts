import type { MoveReview, Review } from '../api/analysis'
import type { GameState } from '../api/games'
import { gameState } from './factories'

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

function move(partial: Partial<MoveReview> & Pick<MoveReview, 'ply' | 'uci' | 'san'>): MoveReview {
  return {
    color: partial.ply % 2 === 0 ? 'white' : 'black',
    classification: 'best',
    symbol: '★',
    win_before: 50,
    win_after: 50,
    delta: 0,
    accuracy: 100,
    best_uci: partial.uci,
    best_san: partial.san,
    best_line: [partial.san],
    played_line: [],
    ...partial,
  }
}

/** Fool's mate, reviewed from white's side: 1.f3?! e5 2.g4?? Qh4#. */
export const FOOLS_GAME: GameState = gameState({
  id: 3,
  status: 'finished',
  result: '0-1',
  termination: 'checkmate',
  initial_fen: START,
  fen: 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3',
  move_count: 4,
  analysis_status: 'done',
})

export const FOOLS_REVIEW: Review = {
  game_id: 3,
  perspective: 'white',
  opening: { eco: 'A00', name: 'Barnes Opening' },
  white: {
    accuracy: 41.2,
    counts: {
      book: 0,
      brilliant: 0,
      great: 0,
      best: 0,
      excellent: 0,
      good: 0,
      inaccuracy: 1,
      mistake: 0,
      blunder: 1,
      miss: 0,
    },
  },
  black: {
    accuracy: 100,
    counts: {
      book: 0,
      brilliant: 0,
      great: 0,
      best: 2,
      excellent: 0,
      good: 0,
      inaccuracy: 0,
      mistake: 0,
      blunder: 0,
      miss: 0,
    },
  },
  key_moments: [2, 0],
  moves: [
    move({
      ply: 0,
      uci: 'f2f3',
      san: 'f3',
      classification: 'inaccuracy',
      symbol: '?!',
      win_before: 52,
      win_after: 45,
      delta: 7,
      best_uci: 'e2e4',
      best_san: 'e4',
      best_line: ['e4', 'e5', 'Nf3'],
      played_line: ['e5', 'g4'],
    }),
    move({ ply: 1, uci: 'e7e5', san: 'e5' }),
    move({
      ply: 2,
      uci: 'g2g4',
      san: 'g4',
      classification: 'blunder',
      symbol: '??',
      win_before: 43,
      win_after: 0,
      delta: 43,
      best_uci: 'b1c3',
      best_san: 'Nc3',
      best_line: ['Nc3', 'Nc6'],
      played_line: ['Qh4#'],
    }),
    move({ ply: 3, uci: 'd8h4', san: 'Qh4#' }),
  ],
  evals: [
    { win: 52, cp: 20, mate: null },
    { win: 45, cp: -40, mate: null },
    { win: 43, cp: -50, mate: null },
    { win: 0, cp: null, mate: -1 },
    { win: 0, cp: null, mate: null },
  ],
}
