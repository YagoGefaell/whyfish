"""What an engine line leads to: material, mate, captures, promotion and motifs. Pure."""

from dataclasses import dataclass

import chess

from app.analysis.consequence import Consequence, consequence
from app.analysis.detectors.common import PieceOn, require_piece
from app.analysis.detectors.motifs import Motif, motifs_in_line
from app.analysis.winprob import win_percent
from app.config import FACTS, FactThresholds


@dataclass(frozen=True)
class Capture:
    index: int  # ply of the line
    by: PieceOn  # the capturing piece, on its origin square
    captured: PieceOn


@dataclass(frozen=True)
class LineOutcome:
    """An engine line from the point of view of the side to move at its start (the mover)."""

    name: str  # "played" | "best" | "second"
    base_ply: int  # game position the line starts from (= ply of the move it begins with)
    ucis: tuple[str, ...]
    sans: tuple[str, ...]
    # Mover's material change at the consequence point of the line (SPEC §5.3): resolved,
    # never in the middle of an exchange.
    material: int
    consequence: Consequence
    # Mover's point of view: > 0 the mover mates in N moves, < 0 the mover is mated in N.
    mate: int | None
    win: float  # mover's win% for this line
    captures: tuple[Capture, ...]  # up to the consequence point (the whole line if none)
    motifs: tuple[Motif, ...]
    promotion: int | None  # ply of the first promotion, if any

    @property
    def first(self) -> str | None:
        return self.sans[0] if self.sans else None

    @property
    def last_mover_capture(self) -> int | None:
        """Ply of the mover's last counted capture (the gain is visible in the line up to it)."""
        own = [c.index for c in self.captures if c.index % 2 == 0]
        return own[-1] if own else None


def line_outcome(
    name: str,
    board: chess.Board,
    ucis: tuple[str, ...],
    cp: int | None,
    mate: int | None,
    base_ply: int,
    t: FactThresholds = FACTS,
) -> LineOutcome:
    """`cp` / `mate` are the engine score of the line for the side to move in `board`."""
    cons = consequence(board, ucis, t)
    b = board.copy(stack=False)
    sans: list[str] = []
    valid: list[str] = []
    captures: list[Capture] = []
    promotion: int | None = None
    window = cons.ply + 1 if cons.ply is not None else t.consequence_max_plies
    for index, uci in enumerate(ucis):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in b.legal_moves:
            break
        if index < window:
            if b.is_capture(move):
                victim = (
                    move.to_square
                    if not b.is_en_passant(move)
                    else chess.square(
                        chess.square_file(move.to_square), chess.square_rank(move.from_square)
                    )
                )
                captures.append(
                    Capture(index, require_piece(b, move.from_square), require_piece(b, victim))
                )
            if move.promotion and promotion is None:
                promotion = index
        sans.append(b.san(move))
        valid.append(uci)
        b.push(move)
    win = win_percent(cp, mate) if (cp is not None or mate is not None) else 50.0
    return LineOutcome(
        name=name,
        base_ply=base_ply,
        ucis=tuple(valid),
        sans=tuple(sans),
        material=cons.material,
        consequence=cons,
        mate=mate,
        win=win,
        captures=tuple(captures),
        motifs=motifs_in_line(board, tuple(valid), t.motif_plies),
        promotion=promotion,
    )
