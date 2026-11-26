"""The main idea of a move: the one thing a level-1 explanation talks about.

Chosen from the facts by a fixed priority (SPEC §5.1):
- errors: mate allowed > mate missed > piece left hanging > tactic allowed > material lost >
  material missed > positional comment;
- missed opportunities (✗): mate missed > material missed first;
- great move (!): why the alternatives failed (the second MultiPV line) first;
- brilliant (!!): the sacrifice first;
- good moves: mate > material won > threat created > threat parried.

Each idea carries the board annotations that show it (position after the move) and the names
of the facts it relies on (`used`, shown in the review report).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Literal

import chess

from app.analysis.detectors.common import PieceOn, piece_on, require_piece
from app.analysis.detectors.lines import LineOutcome
from app.analysis.detectors.motifs import Motif
from app.analysis.detectors.threats import Parried, Threat
from app.analysis.facts import MoveFacts
from app.analysis.types import Classification
from app.config import FACTS, FactThresholds

C = Classification
ERRORS = (C.INACCURACY, C.MISTAKE, C.BLUNDER, C.MISS)
GOOD = (C.BRILLIANT, C.GREAT, C.BEST)
# Plies of the refutation in which the capture of a hanging piece must happen.
_HANGING_WINDOW = 4


class IdeaKind(StrEnum):
    ALLOWS_MATE = "allows_mate"
    MISSED_MATE = "missed_mate"
    HANGING = "hanging"
    TACTIC_ALLOWED = "tactic_allowed"
    LOSES_MATERIAL = "loses_material"
    MISSED_GAIN = "missed_gain"
    POSITIONAL = "positional"
    MATE = "mate"
    ONLY_MOVE = "only_move"
    SACRIFICE = "sacrifice"
    WINS_MATERIAL = "wins_material"
    THREAT_CREATED = "threat_created"
    PARRIES = "parries"
    BOOK = "book"
    SLIGHTLY_WORSE = "slightly_worse"


Role = Literal["threat", "danger", "attack", "target"]


@dataclass(frozen=True)
class Annotation:
    """Drawn on the position after the move. threat = red arrow (opponent's threat), danger =
    red square (piece in danger), attack = amber arrow (what a good move attacks), target =
    amber square (piece that could be won / was saved)."""

    kind: Literal["arrow", "square"]
    role: Role
    square: str | None = None
    from_square: str | None = None
    to_square: str | None = None


def arrow(from_square: str, to_square: str, role: Role) -> Annotation:
    return Annotation("arrow", role, from_square=from_square, to_square=to_square)


def square(name: str, role: Role) -> Annotation:
    return Annotation("square", role, square=name)


@dataclass(frozen=True)
class Idea:
    kind: IdeaKind
    used: tuple[str, ...]
    annotations: tuple[Annotation, ...] = ()
    piece: PieceOn | None = None  # hanging / sacrificed / won piece
    index: int | None = None  # ply of the relevant line (capturing reply, motif move...)
    motif: Motif | None = None
    gain: int = 0  # material won or lost, points
    threats: tuple[Threat, ...] = ()
    parried: Parried | None = None


def choose_idea(facts: MoveFacts, t: FactThresholds = FACTS) -> Idea | None:
    c = facts.classification
    if c == C.BOOK:
        return Idea(IdeaKind.BOOK, ("opening",) if facts.opening else ())
    if c in (C.EXCELLENT, C.GOOD):
        return _slightly_worse(facts, t)
    if c in ERRORS:
        order: list[Callable[[MoveFacts, FactThresholds], Idea | None]] = [
            _allows_mate,
            _missed_mate,
            _hanging,
            _tactic_allowed,
            _loses_material,
            _missed_gain,
        ]
        if c == C.MISS:
            order = [_missed_mate, _missed_gain, *order[:1], *order[2:5]]
        return _first(order, facts, t) or _positional(facts)
    if c in GOOD:
        if c == C.BEST and (facts.recapture or facts.only_move):
            return None  # obvious: nothing to explain
        good: list[Callable[[MoveFacts, FactThresholds], Idea | None]] = [
            _mate,
            _wins_material,
            _threat_created,
            _parries,
        ]
        if c == C.GREAT:
            good.insert(0, _only_move)
        if c == C.BRILLIANT:
            good.insert(0, _sacrifice)
        return _first(good, facts, t)
    return None


def _first(
    detectors: Iterable[Callable[[MoveFacts, FactThresholds], Idea | None]],
    facts: MoveFacts,
    t: FactThresholds,
) -> Idea | None:
    for detector in detectors:
        idea = detector(facts, t)
        if idea is not None:
            return _with_valid_annotations(idea, facts, t.annotations_level1_max)
    return None


def _with_valid_annotations(idea: Idea, facts: MoveFacts, limit: int) -> Idea:
    return replace(idea, annotations=valid_annotations(idea.annotations, facts, limit))


def valid_annotations(
    annotations: Iterable[Annotation], facts: MoveFacts, limit: int
) -> tuple[Annotation, ...]:
    """Drop duplicates and arrows that do not start on a piece in the position after the move."""
    board = chess.Board(facts.fen_after)
    out: list[Annotation] = []
    for ann in annotations:
        if ann in out:
            continue
        if ann.kind == "arrow":
            if ann.from_square is None or ann.to_square is None or ann.from_square == ann.to_square:
                continue
            if board.piece_at(chess.parse_square(ann.from_square)) is None:
                continue
        out.append(ann)
        if len(out) == limit:
            break
    return tuple(out)


# --- helpers -------------------------------------------------------------------------------


def _material_error(facts: MoveFacts, t: FactThresholds) -> bool:
    """The refutation loses material at its consequence point, and the best line less."""
    pl, bl = facts.played_line, facts.best_line
    if pl is None or pl.material > -t.material_min:
        return False
    return bl is None or bl.material - pl.material >= t.material_min


def _reply_arrow(line: LineOutcome, index: int) -> Annotation | None:
    if index >= len(line.ucis):
        return None
    uci = line.ucis[index]
    return arrow(uci[:2], uci[2:4], "threat")


def _king_square(facts: MoveFacts, color: str) -> str | None:
    board = chess.Board(facts.fen_after)
    king = board.king(color == "white")
    return chess.square_name(king) if king is not None else None


def _opponent(color: str) -> str:
    return "black" if color == "white" else "white"


def _still_there(facts: MoveFacts, piece: PieceOn) -> bool:
    return piece_on(chess.Board(facts.fen_after), chess.parse_square(piece.square)) == piece


def _motif_annotations(motif: Motif, role_target: Role, by_role: Role) -> list[Annotation]:
    if motif.kind == "pin":
        pinned, behind = motif.targets
        return [arrow(motif.by.square, behind.square, by_role), square(pinned.square, role_target)]
    return [square(t.square, role_target) for t in motif.targets if not t.is_king] + [
        arrow(motif.by.square, t.square, by_role) for t in motif.targets[:1]
    ]


def shown_gain(line: LineOutcome, t: FactThresholds) -> bool:
    """The line wins material and its consequence point (SPEC §5.3) is inside the line, close
    enough to be shown ("Ver por qué" replays up to it)."""
    return shown_change(line, t) and line.material >= t.material_min


def shown_change(line: LineOutcome, t: FactThresholds) -> bool:
    """The line's material consequence is settled within `consequence_text_max_plies`."""
    c = line.consequence
    return (
        c.kind == "material"
        and c.settled
        and c.ply is not None
        and c.ply + 1 <= t.consequence_text_max_plies
    )


def visible_gain(line: LineOutcome, t: FactThresholds) -> bool:
    """The line wins material in a way the text can show and the evaluation backs."""
    return shown_gain(line, t) and line.win >= t.gain_claim_min_win


def won_piece(line: LineOutcome, gainer_parity: int, gain: int) -> PieceOn | None:
    """The piece won along the line when it explains the net gain: the biggest piece captured
    by the gaining side, worth the gain or up to two points more (a piece for a pawn or two),
    as long as the other side only captured pawns back (otherwise it was an exchange).
    """
    taken = [c.captured for c in line.captures if c.index % 2 == gainer_parity]
    back = [c.captured for c in line.captures if c.index % 2 != gainer_parity]
    if not taken or gain <= 0 or any(p.piece != "pawn" for p in back):
        return None
    biggest = max(taken, key=lambda p: p.value)
    return biggest if 0 <= biggest.value - gain <= 2 else None


# --- errors --------------------------------------------------------------------------------


def _allows_mate(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl, bl = facts.played_line, facts.best_line
    if pl is None or pl.mate is None or pl.mate >= 0 or len(pl.sans) < 2:
        return None
    if bl is not None and bl.mate is not None and bl.mate < 0:
        return None  # mated anyway
    anns = [a for a in (_reply_arrow(pl, 1),) if a]
    king = _king_square(facts, facts.color)
    if king:
        anns.append(square(king, "danger"))
    return Idea(
        IdeaKind.ALLOWS_MATE, ("played_line.mate", "played_line", "best_line"), tuple(anns), index=1
    )


def _missed_mate(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl, bl = facts.played_line, facts.best_line
    if bl is None or bl.mate is None or bl.mate <= 0:
        return None
    if pl is not None and pl.mate is not None and pl.mate > 0:
        return None
    king = _king_square(facts, _opponent(facts.color))
    anns = (square(king, "target"),) if king else ()
    return Idea(IdeaKind.MISSED_MATE, ("best_line.mate", "best_line"), anns)


def _hanging(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    """Only if the hanging piece is what the refutation ends up costing (its consequence
    point, SPEC §5.3): a pawn left en prise is not the story if the line loses the queen."""
    pl = facts.played_line
    if pl is None or not _material_error(facts, t):
        return None
    for hanging in facts.played.hanging:
        if hanging.piece.piece not in pl.consequence.lost:
            continue
        for capture in pl.captures:
            if (
                capture.index % 2 == 1
                and capture.index < _HANGING_WINDOW
                and capture.captured.square == hanging.piece.square
            ):
                attacker = capture.by.square if capture.index == 1 else hanging.attackers[0]
                anns = (
                    square(hanging.piece.square, "danger"),
                    arrow(attacker, hanging.piece.square, "threat"),
                )
                return Idea(
                    IdeaKind.HANGING,
                    ("played.hanging", "played_line", "best_line"),
                    anns,
                    piece=hanging.piece,
                    index=capture.index,
                    gain=hanging.loss,
                )
    return None


def _tactic_allowed(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl = facts.played_line
    if pl is None or not _material_error(facts, t) or not shown_change(pl, t):
        return None
    for motif in pl.motifs:
        if motif.index % 2 == 1:
            reply = _reply_arrow(pl, motif.index)
            anns = ([reply] if reply else []) + _motif_annotations(motif, "danger", "threat")
            return Idea(
                IdeaKind.TACTIC_ALLOWED,
                ("played_line.motifs", "played_line", "best_line"),
                tuple(anns),
                piece=won_piece(pl, 1, -pl.material),
                index=motif.index,
                motif=motif,
                gain=-pl.material,
            )
    return None


def _loses_material(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl = facts.played_line
    if pl is None or not _material_error(facts, t) or len(pl.sans) < 2:
        return None
    lost = won_piece(pl, 1, -pl.material)
    anns: list[Annotation] = [a for a in (_reply_arrow(pl, 1),) if a]
    if lost and _still_there(facts, lost):
        anns.append(square(lost.square, "danger"))
    return Idea(
        IdeaKind.LOSES_MATERIAL,
        ("played_line.material", "played_line", "best_line"),
        tuple(anns),
        piece=lost,
        index=1,
        gain=-pl.material,
    )


def _missed_gain(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl, bl = facts.played_line, facts.best_line
    if pl is None or bl is None or not shown_gain(bl, t):
        return None
    gain = bl.material - pl.material
    if gain < t.material_min:
        return None
    motif = next((m for m in bl.motifs if m.index == 0), None)
    won = won_piece(bl, 0, bl.material)
    anns: list[Annotation] = []
    used = ["best_line.material", "best_line", "played_line"]
    if motif:
        used.append("best_line.motifs")
        anns += [square(p.square, "target") for p in motif.targets if not p.is_king]
    elif won and _still_there(facts, won):
        anns.append(square(won.square, "target"))
    return Idea(
        IdeaKind.MISSED_GAIN, tuple(used), tuple(anns), piece=won, motif=motif, gain=bl.material
    )


def _positional(facts: MoveFacts) -> Idea:
    """Fallback for errors with no tactical fact: only positional facts, possibly none."""
    used: list[str] = []
    played, best = facts.played, facts.best
    if played.weakens_king:
        used.append("played.weakens_king")
    minor = facts.classification in (C.INACCURACY, C.EXCELLENT, C.GOOD)
    if minor and any(p.kind in ("doubled", "isolated", "opponent_passed") for p in played.pawns):
        used.append("played.pawns")
    if best is not None:
        if best.castles:
            used.append("best.castles")
        elif best.develops and not played.develops:
            used.append("best.develops")
        elif best.threats:
            used.append("best.threats")
        elif best.parried:
            used.append("best.parried")
    return Idea(IdeaKind.POSITIONAL, tuple(used))


def _slightly_worse(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    if facts.best is None or facts.best_line is None:
        return None
    pl, bl = facts.played_line, facts.best_line
    # Same rule as every gain claim: the best line must show the gain (a capture within the
    # plies the text shows, not only the SEE settlement at its end) and the evaluation back it.
    if pl is not None and bl.material - pl.material >= t.material_min and visible_gain(bl, t):
        return Idea(
            IdeaKind.SLIGHTLY_WORSE,
            ("best_line.material", "best_line", "played_line"),
            gain=bl.material - pl.material,
        )
    return Idea(IdeaKind.SLIGHTLY_WORSE, _positional(facts).used)


# --- good moves ----------------------------------------------------------------------------


def _mate(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl = facts.played_line
    if pl is None or pl.mate is None or pl.mate <= 0:
        return None
    king = _king_square(facts, _opponent(facts.color))
    anns = (square(king, "target"),) if king else ()
    return Idea(IdeaKind.MATE, ("played_line.mate", "played_line"), anns)


def _only_move(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    second = facts.second_line
    if second is None or not second.sans:
        return None
    anns = tuple(
        arrow(th.attackers[0], th.target.square, "attack") for th in facts.played.threats[:2]
    )
    return Idea(IdeaKind.ONLY_MOVE, ("second_line", "played_line"), anns)


def _sacrifice(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    """Only from `facts.sacrifice`: a legal capture with favourable SEE for the opponent,
    verified by the engine line where it is taken (`facts.sacrifice_line`, ply 1)."""
    sac, line = facts.sacrifice, facts.sacrifice_line
    if sac is None or line is None or len(line.sans) < 2:
        return None
    after = chess.Board(facts.fen_after)
    piece = require_piece(after, chess.parse_square(sac.square))
    anns: list[Annotation] = [square(piece.square, "danger")]
    anns += [arrow(th.attackers[0], th.target.square, "attack") for th in facts.played.threats[:2]]
    return Idea(
        IdeaKind.SACRIFICE,
        ("sacrifice", "sacrifice_line"),
        tuple(anns),
        piece=piece,
        index=1,
        gain=sac.amount,
    )


def _wins_material(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    pl = facts.played_line
    if pl is None or facts.recapture or not visible_gain(pl, t):
        return None
    motif = next((m for m in pl.motifs if m.index == 0), None)
    won = won_piece(pl, 0, pl.material)
    anns: list[Annotation] = []
    used = ["played_line.material", "played_line"]
    if motif:
        used.append("played_line.motifs")
        anns += [arrow(motif.by.square, p.square, "attack") for p in motif.targets]
    elif won:
        captured_now = facts.played.captured
        if captured_now != won and _still_there(facts, won):
            anns.append(square(won.square, "target"))
    return Idea(
        IdeaKind.WINS_MATERIAL,
        tuple(used),
        tuple(anns),
        piece=won,
        index=pl.last_mover_capture,
        motif=motif,
        gain=pl.material,
    )


def _threat_created(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    threats = facts.played.threats
    if not threats:
        return None
    anns = tuple(arrow(th.attackers[0], th.target.square, "attack") for th in threats[:3])
    return Idea(IdeaKind.THREAT_CREATED, ("played.threats",), anns, threats=threats)


def _parries(facts: MoveFacts, t: FactThresholds) -> Idea | None:
    if not facts.played.parried:
        return None
    parried = facts.played.parried[0]
    anns = (square(parried.piece_after.square, "target"),) if parried.piece_after else ()
    return Idea(IdeaKind.PARRIES, ("played.parried",), anns, parried=parried)
