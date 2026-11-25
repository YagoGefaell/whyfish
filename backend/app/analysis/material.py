"""Material counting and static exchange evaluation (SEE). Pure functions."""

import chess

PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def material(board: chess.Board, color: chess.Color) -> int:
    return sum(value * len(board.pieces(kind, color)) for kind, value in PIECE_VALUES.items())


def balance(board: chess.Board, color: chess.Color) -> int:
    """Material of `color` minus the opponent's."""
    return material(board, color) - material(board, not color)


def captured_value(board: chess.Board, move: chess.Move) -> int:
    """Value of the piece `move` captures in `board` (before the move); 0 if none."""
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    piece = board.piece_at(move.to_square)
    return PIECE_VALUES[piece.piece_type] if piece else 0


def see(board: chess.Board, square: chess.Square) -> int:
    """Material the side to move can win by starting a capture sequence on `square`.

    Both sides capture with their least valuable piece and may stop at any point, so the
    result is >= 0. Uses legal moves, so pins and x-rays are handled.
    """
    target = board.piece_at(square)
    if target is None or target.color == board.turn:
        return 0
    captures = [m for m in board.legal_moves if m.to_square == square]
    if not captures:
        return 0

    # Least valuable attacker first; prefer queen promotion when a pawn captures on the 8th.
    def attacker_value(m: chess.Move) -> tuple[int, int]:
        piece = board.piece_at(m.from_square)
        assert piece is not None
        return PIECE_VALUES[piece.piece_type] or 100, -(m.promotion or 0)

    move = min(captures, key=attacker_value)
    gain = PIECE_VALUES[target.piece_type]
    if move.promotion:
        gain += PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]
    board.push(move)
    try:
        return max(0, gain - see(board, square))
    finally:
        board.pop()


def newly_en_prise(
    before: chess.Board, move: chess.Move, min_gain: int
) -> list[tuple[chess.Square, int]]:
    """Mover's pieces that are en prise after `move` but were not before.

    En prise = the opponent wins at least `min_gain` points (net of what `move` itself
    captured) by starting a capture sequence on that square. Kings are ignored.
    """
    mover = before.turn
    after = before.copy(stack=False)
    taken = captured_value(before, move)
    after.push(move)
    result: list[tuple[chess.Square, int]] = []
    for square, piece in after.piece_map().items():
        if piece.color != mover or piece.piece_type == chess.KING:
            continue
        gain = see(after, square) - taken
        if gain < min_gain:
            continue
        if square != move.to_square and _was_en_prise(before, square, min_gain):
            continue
        result.append((square, gain))
    return result


def _was_en_prise(before: chess.Board, square: chess.Square, min_gain: int) -> bool:
    if before.is_check():
        return False  # a null move is not meaningful here; treat as not en prise before
    flipped = before.copy(stack=False)
    flipped.push(chess.Move.null())
    return see(flipped, square) >= min_gain
