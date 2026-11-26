"""Hand-made positions with engine lines, for idea/template tests (no engine)."""

from collections.abc import Sequence

import chess

from app.analysis.facts import MoveFacts, build_move_facts
from app.analysis.types import Classification, EngineLine, PositionEval
from app.analysis.winprob import line_win

C = Classification


def line(*moves: str, cp: int | None = None, mate: int | None = None) -> EngineLine:
    return EngineLine(moves=tuple(moves), cp=cp, mate=mate)


def make_facts(
    fen: str,
    played: str,
    before: Sequence[EngineLine],
    after: Sequence[EngineLine],
    classification: Classification,
    *,
    history: Sequence[str] = (),
    opening: str | None = None,
    after_error: bool = False,
) -> MoveFacts:
    """`fen` + `history` (SAN) is the position before `played` (UCI)."""
    board = chess.Board(fen)
    for san in history:
        board.push_san(san)
    move = chess.Move.from_uci(played)
    after_board = board.copy()
    after_board.push(move)
    before_eval = PositionEval(lines=tuple(before))
    terminal = 0.0 if after_board.is_checkmate() else None
    after_eval = PositionEval(lines=tuple(after), terminal_win=terminal if not after else None)
    win_before = line_win(before[0])
    win_after = next(
        (line_win(ln) for ln in before if ln.move == played),
        100.0 - line_win(after[0]) if after else 100.0,
    )
    return build_move_facts(
        board,
        move,
        before_eval,
        after_eval,
        ply=len(board.move_stack),
        classification=classification,
        win_before=win_before,
        win_after=win_after,
        delta=max(0.0, win_before - win_after),
        opening=opening,
        after_opponent_error=after_error,
    )


START = chess.STARTING_FEN


def fools_mate_g4() -> MoveFacts:
    """1. f3 e5 2. g4?? allows Qh4#."""
    return make_facts(
        START,
        "g2g4",
        [line("e2e3", "d8h4", cp=-60), line("g2g4", "d8h4", mate=-1)],
        [line("d8h4", mate=1)],
        C.BLUNDER,
        history=["f3", "e5"],
    )


def fools_mate_missed() -> MoveFacts:
    """1. f3 e5 2. g4 d5? missed Qh4#."""
    return make_facts(
        START,
        "d7d5",
        [line("d8h4", mate=1), line("d7d5", "e2e3", cp=150)],
        [line("e2e3", cp=-150)],
        C.MISS,
        history=["f3", "e5", "g4"],
        after_error=True,
    )


AFTER_NF3 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"


def queen_to_g5() -> MoveFacts:
    """2... Qg5?? hangs the queen to Nxg5."""
    return make_facts(
        AFTER_NF3,
        "d8g5",
        [line("b8c6", "f1b5", cp=-30)],
        [line("f3g5", "f8e7", cp=900)],
        C.BLUNDER,
    )


KNIGHT_C3 = "4k3/8/8/8/1p6/2N5/3B4/4K3 w - - 0 1"


def knight_left_hanging() -> MoveFacts:
    """The c3 knight is attacked by a pawn and white plays Be3: bxc3."""
    return make_facts(
        KNIGHT_C3,
        "d2e3",
        [line("c3d5", "e8d7", cp=200), line("e1e2", "b4c3", cp=-100)],
        [line("b4c3", "e3c1", cp=150)],
        C.MISTAKE,
    )


def only_move_nd5() -> MoveFacts:
    """Same position: Nd5 is the only good move (great move)."""
    return make_facts(
        KNIGHT_C3,
        "c3d5",
        [line("c3d5", "e8d7", cp=200), line("e1e2", "b4c3", cp=-100)],
        [line("e8d7", "d5b4", cp=-200)],
        C.GREAT,
    )


FORK = "r3k3/7p/8/1N6/8/8/8/4K3 b - - 0 1"


def allows_fork() -> MoveFacts:
    """1... h6? allows Nc7+ forking king and rook."""
    return make_facts(
        FORK,
        "h7h6",
        [line("a8b8", "b5d6", cp=-300)],
        [line("b5c7", "e8d7", "c7a8", cp=900)],
        C.MISTAKE,
    )


HANGING_KNIGHT = "4k3/8/8/3n4/8/8/8/3QK3 w - - 0 1"


def missed_knight() -> MoveFacts:
    return make_facts(
        HANGING_KNIGHT,
        "e1e2",
        [line("d1d5", "e8e7", cp=900), line("e1e2", "d5f4", cp=0)],
        [line("d5f4", "e2f3", cp=0)],
        C.BLUNDER,
    )


def takes_knight() -> MoveFacts:
    return make_facts(
        HANGING_KNIGHT,
        "d1d5",
        [line("d1d5", "e8e7", cp=900), line("e1e2", "d5f4", cp=0)],
        [line("e8e7", "d5b7", cp=-900)],
        C.BEST,
    )


def book_e4() -> MoveFacts:
    return make_facts(
        START,
        "e2e4",
        [line("e2e4", "e7e5", cp=30)],
        [line("e7e5", cp=-30)],
        C.BOOK,
        opening="King's Pawn Game",
    )


def good_a3() -> MoveFacts:
    """a3 is fine, Nf3 developed a piece."""
    return make_facts(
        START,
        "a2a3",
        [line("g1f3", "d7d5", cp=30), line("a2a3", "e7e5", cp=0)],
        [line("e7e5", cp=0)],
        C.GOOD,
    )


def recapture() -> MoveFacts:
    """1. e4 d5 2. exd5 Qxd5: the obvious recapture needs no explanation."""
    return make_facts(
        START,
        "d8d5",
        [line("d8d5", "b1c3", cp=-30)],
        [line("b1c3", cp=30)],
        C.BEST,
        history=["e4", "d5", "exd5"],
    )


KNIGHT_SAC = "6k1/5p1p/6p1/8/3N4/8/5PPP/6K1 w - - 0 1"


def knight_sacrifice() -> MoveFacts:
    """Nf5!! leaves the knight to the g6 pawn; the position stays balanced."""
    return make_facts(
        KNIGHT_SAC,
        "d4f5",
        [line("d4f5", "g6f5", cp=-20), line("d4e2", cp=-40)],
        [line("g6f5", cp=20)],
        C.BRILLIANT,
    )


def declined_knight_sacrifice() -> MoveFacts:
    """Nf5!!, declined: taking is not even among the opponent's lines (MultiPV bound)."""
    return make_facts(
        KNIGHT_SAC,
        "d4f5",
        [line("d4f5", "g8h8", cp=50), line("d4e2", cp=40)],
        [line("g8h8", cp=-50), line("h7h5", cp=-60), line("f7f6", cp=-80)],
        C.BRILLIANT,
    )


BD2_IN_CHECK = "rn1qk2r/ppp2ppp/4p1B1/3n4/1b1P4/4PN2/PP3PPP/RNBQK2R w KQkq - 1 8"


def forced_loss_labelled_brilliant() -> MoveFacts:
    """8.Bd2 in check, with the old wrong !! label: no legal move saved the g6 bishop."""
    return make_facts(
        BD2_IN_CHECK,
        "c1d2",
        [line("c1d2", "h7g6", "d2b4", "d5b4", "d1b3", "c7c5", cp=128), line("b1c3", cp=55)],
        [line("h7g6", "d2b4", cp=-128)],
        C.BRILLIANT,
    )


ALL = [
    fools_mate_g4,
    fools_mate_missed,
    queen_to_g5,
    knight_left_hanging,
    only_move_nd5,
    allows_fork,
    missed_knight,
    takes_knight,
    book_e4,
    good_a3,
    recapture,
    knight_sacrifice,
    declined_knight_sacrifice,
    forced_loss_labelled_brilliant,
]
