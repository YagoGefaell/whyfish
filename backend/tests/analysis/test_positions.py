import chess

from app.analysis.positions import engine_board, game_positions, position_key


def test_engine_board_keeps_only_reversible_history() -> None:
    board = chess.Board()
    for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f3g1"]:
        board.push_uci(uci)
    eb = engine_board(board)
    assert [m.uci() for m in eb.move_stack] == ["g1f3", "b8c6", "f3g1"]
    assert eb.fen() == board.fen()
    assert eb.root().fen().startswith("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w")


def test_engine_board_detects_repetition() -> None:
    board = chess.Board()
    for uci in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
        board.push_uci(uci)
    assert engine_board(board).is_repetition(3)


def test_same_position_after_irreversible_move_shares_key() -> None:
    a = chess.Board()
    for uci in ["e2e4", "e7e5", "d2d4"]:
        a.push_uci(uci)
    b = chess.Board()
    for uci in ["d2d4", "e7e5", "e2e4"]:
        b.push_uci(uci)
    assert position_key(engine_board(a)) == position_key(engine_board(b))


def test_different_reversible_history_changes_key() -> None:
    a, b = chess.Board(), chess.Board()
    for uci in ["e2e4", "e7e5"]:
        a.push_uci(uci)
        b.push_uci(uci)
    for uci in ["g1f3", "g8f6", "f3g1", "f6g8"]:
        b.push_uci(uci)
    assert a.board_fen() == b.board_fen()
    assert position_key(engine_board(a)) != position_key(engine_board(b))


def test_game_positions_marks_terminal_positions() -> None:
    positions = game_positions(chess.STARTING_FEN, ["f2f3", "e7e5", "g2g4", "d8h4"])
    assert len(positions) == 5
    assert [p.terminal is not None for p in positions] == [False, False, False, False, True]
    final = positions[-1].terminal
    assert final is not None and final.terminal_win == 0.0  # white (to move) is mated
