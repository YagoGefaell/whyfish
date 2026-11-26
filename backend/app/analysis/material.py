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


def left_en_prise(
    before: chess.Board, move: chess.Move, min_gain: int
) -> list[tuple[chess.Square, int]]:
    """Mover's pieces that `move` leaves en prise (SPEC §3.1): a sacrifice.

    En prise = the opponent wins at least `min_gain` points (net of what `move` itself
    captured) by starting a capture sequence on that square. Kings are ignored. A piece counts
    if it was not en prise before the move, or if it already was but some other legal move
    would have made it safe (so a trapped piece that is lost anyway does not count).
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
        already_lost = (
            square != move.to_square
            and _was_en_prise(before, square, min_gain)
            and not _could_be_saved(before, square, move, min_gain)
        )
        if already_lost:
            continue
        result.append((square, gain))
    return result


def _was_en_prise(before: chess.Board, square: chess.Square, min_gain: int) -> bool:
    # Also when the mover is in check: the null move only hands the turn over, which is what
    # "could the opponent take it if it were their move" means (a piece attacked while we are
    # in check is usually lost; `_could_be_saved` then decides).
    flipped = before.copy(stack=False)
    flipped.push(chess.Move.null())
    return see(flipped, square) >= min_gain


def _could_be_saved(
    before: chess.Board, square: chess.Square, played: chess.Move, min_gain: int
) -> bool:
    """Whether some legal move other than `played` leaves the piece on `square` safe.

    "Safe" covers moving it away, defending it, blocking or capturing the attacker: after that
    move the opponent can no longer win `min_gain` points (net of what the move captured) on
    the piece's (possibly new) square.
    """
    piece = before.piece_at(square)
    for candidate in before.legal_moves:
        if candidate == played:
            continue
        b = before.copy(stack=False)
        taken = captured_value(before, candidate)
        b.push(candidate)
        target = candidate.to_square if candidate.from_square == square else square
        if b.piece_at(target) != piece and candidate.promotion is None:
            continue
        if see(b, target) - taken < min_gain:
            return True
    return False


_INFINITY = 10_000


def resolved_balance(board: chess.Board, color: chess.Color, max_plies: int) -> int:
    """Balance of `color` once the pending captures are played out (quiescence search).

    The side to move may stand pat (keep the static balance) unless it is in check, in which
    case every evasion is searched. Captures and promotions only, at most `max_plies` deep.
    Mate is not scored: this is a material measure.
    """
    value = _quiescence(board.copy(stack=False), max_plies, -_INFINITY, _INFINITY)
    return value if board.turn == color else -value


def balance_after(board: chess.Board, move: chess.Move, color: chess.Color, max_plies: int) -> int:
    """`resolved_balance` of `color` after `move` (the opponent then resolves the captures)."""
    after = board.copy(stack=False)
    after.push(move)
    return resolved_balance(after, color, max_plies)


def _quiescence(board: chess.Board, depth: int, alpha: int, beta: int) -> int:
    """Negamax value (material, side to move's point of view) with alpha-beta."""
    static = balance(board, board.turn)
    in_check = board.is_check()
    if depth == 0:
        return static
    if in_check:
        moves = list(board.legal_moves)
        if not moves:
            return static
    else:
        if static >= beta:
            return static
        alpha = max(alpha, static)
        moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
    moves.sort(key=lambda m: _capture_order(board, m), reverse=True)
    best = static if not in_check else -_INFINITY
    for move in moves:
        board.push(move)
        value = -_quiescence(board, depth - 1, -beta, -alpha)
        board.pop()
        if value > best:
            best = value
        if value > alpha:
            alpha = value
        if alpha >= beta:
            break
    return best


def _capture_order(board: chess.Board, move: chess.Move) -> tuple[int, int]:
    """Most valuable victim first, then least valuable attacker."""
    attacker = board.piece_at(move.from_square)
    attacker_value = PIECE_VALUES[attacker.piece_type] if attacker else 0
    return captured_value(board, move) + (PIECE_VALUES.get(move.promotion or 0, 0)), -attacker_value
