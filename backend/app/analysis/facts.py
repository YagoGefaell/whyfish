"""MoveFacts (SPEC §4): everything an explanation may state about a move, without free text.

Built from the position, the move and the engine lines already stored by the analysis (before
and after the move); no engine call. Pure: testable with fixed FENs and fake evaluations.
"""

from dataclasses import asdict, dataclass
from typing import Any

import chess

from app.analysis import material
from app.analysis.classify import is_obvious_recapture, is_only_move
from app.analysis.detectors.common import PieceOn, piece_on, require_piece
from app.analysis.detectors.lines import LineOutcome, line_outcome
from app.analysis.detectors.motifs import Motif, motifs_of_move
from app.analysis.detectors.structure import (
    PawnChange,
    Phase,
    develops,
    pawn_changes,
    phase,
    weakens_king,
)
from app.analysis.detectors.threats import (
    Hanging,
    Parried,
    Threat,
    hanging_after,
    new_threats,
    parried_threats,
)
from app.analysis.sacrifice import Sacrifice, find_sacrifice
from app.analysis.types import Classification, PositionEval
from app.config import FACTS, FactThresholds


@dataclass(frozen=True)
class MoveEffects:
    """What a move does by itself (computed for the played move and for the best one)."""

    san: str
    uci: str
    piece: PieceOn  # the moved piece, on its destination (promoted piece if it promotes)
    captured: PieceOn | None
    gives_check: bool
    is_mate: bool
    castles: bool
    develops: bool
    weakens_king: bool
    hanging: tuple[Hanging, ...]  # mover's pieces left en prise by this move
    threats: tuple[Threat, ...]  # new threats of the mover after this move
    parried: tuple[Parried, ...]  # opponent threats this move removes
    pawns: tuple[PawnChange, ...]
    motifs: tuple[Motif, ...]  # motifs of this move itself


@dataclass(frozen=True)
class MoveFacts:
    ply: int
    color: str  # the mover
    san: str
    uci: str
    fen_before: str
    fen_after: str
    classification: Classification
    win_before: float
    win_after: float
    delta: float
    phase: Phase
    material_before: int  # mover's material balance before the move (P=1 ... Q=9)
    opening: str | None  # opening name if the position after the move is in the book
    is_best: bool
    only_move: bool
    recapture: bool  # obvious recapture on the square the opponent just captured on
    after_opponent_error: bool  # the opponent's previous move was ? or ??
    played: MoveEffects
    best: MoveEffects | None  # None when the played move is the best one
    # Engine lines from the position before the move, mover's point of view:
    played_line: LineOutcome | None  # the played move, then the opponent's best reply...
    best_line: LineOutcome | None
    second_line: LineOutcome | None  # when the played move is the best: the next option
    # A piece given up (legal capture with favourable SEE for the opponent, not forced,
    # verified by an engine line where it is taken): the same check as the brilliant
    # classification. Templates may only say "entrega" / "material de menos" from this.
    sacrifice: Sacrifice | None
    sacrifice_line: LineOutcome | None  # the verifying line (named "played": it starts with it)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def move_effects(board: chess.Board, move: chess.Move, t: FactThresholds = FACTS) -> MoveEffects:
    after = board.copy(stack=False)
    after.push(move)
    captured_square = move.to_square
    if board.is_en_passant(move):
        captured_square = chess.square(
            chess.square_file(move.to_square), chess.square_rank(move.from_square)
        )
    return MoveEffects(
        san=board.san(move),
        uci=move.uci(),
        piece=require_piece(after, move.to_square),
        captured=piece_on(board, captured_square) if board.is_capture(move) else None,
        gives_check=after.is_check(),
        is_mate=after.is_checkmate(),
        castles=board.is_castling(move),
        develops=develops(board, move, t),
        weakens_king=weakens_king(board, move),
        hanging=hanging_after(board, move, t.material_min),
        threats=new_threats(board, move, t.material_min),
        parried=parried_threats(board, move, t.material_min),
        pawns=pawn_changes(board, move),
        motifs=motifs_of_move(board, move),
    )


def _played_line(
    board: chess.Board,
    move: chess.Move,
    before: PositionEval,
    after: PositionEval,
    ply: int,
    t: FactThresholds,
) -> LineOutcome:
    uci = move.uci()
    for line in before.lines:
        if line.move == uci:
            return line_outcome("played", board, line.moves, line.cp, line.mate, ply, t)
    if after.lines:
        reply = after.lines[0]
        mate = -reply.mate if reply.mate is not None else None
        cp = -reply.cp if reply.cp is not None else None
        return line_outcome("played", board, (uci, *reply.moves), cp, mate, ply, t)
    # Terminal position after the move: mate (the mover mates in 1) or a draw.
    b = board.copy(stack=False)
    b.push(move)
    if b.is_checkmate():
        return line_outcome("played", board, (uci,), None, 1, ply, t)
    return line_outcome("played", board, (uci,), 0, None, ply, t)


def build_move_facts(
    board: chess.Board,
    move: chess.Move,
    before: PositionEval,
    after: PositionEval,
    *,
    ply: int,
    classification: Classification,
    win_before: float,
    win_after: float,
    delta: float,
    opening: str | None,
    after_opponent_error: bool,
    t: FactThresholds = FACTS,
) -> MoveFacts:
    """`board` is the position before the move, with its move history (for recaptures)."""
    after_board = board.copy(stack=False)
    after_board.push(move)
    best_engine = before.lines[0] if before.lines else None
    is_best = best_engine is not None and best_engine.move == move.uci()

    best_line = None
    if best_engine is not None:
        best_line = line_outcome(
            "best", board, best_engine.moves, best_engine.cp, best_engine.mate, ply, t
        )
    second_line = None
    if is_best and len(before.lines) > 1:
        second = before.lines[1]
        second_line = line_outcome("second", board, second.moves, second.cp, second.mate, ply, t)

    best_effects = None
    if best_engine is not None and not is_best:
        best_move = chess.Move.from_uci(best_engine.move)
        if best_move in board.legal_moves:
            best_effects = move_effects(board, best_move, t)

    played_line = _played_line(board, move, before, after, ply, t)
    sacrifice = find_sacrifice(board, move, before, after)
    sacrifice_line = None
    if sacrifice is not None:
        sacrifice_line = line_outcome(
            "played", board, sacrifice.line, sacrifice.cp, sacrifice.mate, ply, t
        )
    return MoveFacts(
        ply=ply,
        color="white" if board.turn == chess.WHITE else "black",
        san=board.san(move),
        uci=move.uci(),
        fen_before=board.fen(),
        fen_after=after_board.fen(),
        classification=classification,
        win_before=win_before,
        win_after=win_after,
        delta=delta,
        phase=phase(board, t),
        material_before=material.balance(board, board.turn),
        opening=opening,
        is_best=is_best,
        only_move=is_only_move(board),
        recapture=is_obvious_recapture(board, move),
        after_opponent_error=after_opponent_error,
        played=move_effects(board, move, t),
        best=best_effects,
        played_line=played_line,
        best_line=best_line,
        second_line=second_line,
        sacrifice=sacrifice,
        sacrifice_line=sacrifice_line,
    )
