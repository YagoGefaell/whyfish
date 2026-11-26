"""Ver por qué (SPEC §5.4): the sequence that leads to a move's consequence, step by step.

Pure: the line (possibly already extended with the engine) comes in, steps with a short
caption each and a final summary go out. The consequence point is the same one the level-1
text uses (`analysis/consequence.py`), so both tell the same story.

- refutation (moves that are not the best): the move played, then the engine's refutation;
- idea: "!" -> the refutation of the second option (why the alternatives failed); "!!" -> the
  line of the sacrifice; a best move with an explanation -> its own line.

Pieces are always named relative to the user ("tu dama", "la torre rival"). In a refutation of
the user's move, the user's later moves are the engine's best defence, not what was played.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import chess

from app.analysis import material
from app.analysis.consequence import Consequence, consequence
from app.analysis.detectors.threats import new_threats
from app.analysis.facts import MoveFacts
from app.analysis.types import Classification
from app.config import FACTS, THRESHOLDS, FactThresholds
from app.explain import spanish as es
from app.explain.marks import MarkedText, MoveRef

C = Classification
Kind = Literal["refutation", "idea"]

REFUTATION = frozenset({C.EXCELLENT, C.GOOD, C.INACCURACY, C.MISTAKE, C.BLUNDER, C.MISS})
IDEA = frozenset({C.GREAT, C.BRILLIANT, C.BEST})

_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


@dataclass(frozen=True)
class Arrow:
    from_square: str
    to_square: str


@dataclass(frozen=True)
class WhyStep:
    index: int  # 0 = the first move of the sequence
    label: str  # "21…dxc3", "22.Rxd8"
    san: str
    uci: str
    fen: str  # position after the move
    color: str  # side that plays it
    caption: str
    defense: bool  # the user's best defence according to the engine (not what was played)
    consequence: bool  # the step where the consequence materialises
    arrows: tuple[Arrow, ...]  # threats created earlier (or now) and executed later


@dataclass(frozen=True)
class Why:
    kind: Kind
    tone: Literal["bad", "good"]  # red (error) / green (idea)
    base_ply: int  # game position the sequence starts from (before the move)
    start_fen: str
    title: str
    alternative: str | None  # SAN of the other move the sequence starts with ("!")
    steps: tuple[WhyStep, ...]
    consequence_ply: int | None  # index of the consequence step
    summary: str  # with [[SAN]] marks
    refs: tuple[MoveRef, ...]  # one per mark of `summary`


@dataclass(frozen=True)
class WhyLine:
    ucis: tuple[str, ...]
    alternative: bool  # starts with another move than the one played (the "!" second option)


def why_kind(classification: Classification) -> Kind | None:
    if classification in REFUTATION:
        return "refutation"
    if classification in IDEA:
        return "idea"
    return None


def why_line(facts: MoveFacts, kind: Kind) -> WhyLine | None:
    """The engine line the sequence replays (before any extension)."""
    if kind == "refutation":
        pl = facts.played_line
        return WhyLine(pl.ucis, False) if pl is not None and pl.ucis else None
    if facts.classification == C.GREAT and facts.second_line and facts.second_line.ucis:
        return WhyLine(facts.second_line.ucis, True)
    if facts.classification == C.BRILLIANT and facts.sacrifice_line is not None:
        return WhyLine(facts.sacrifice_line.ucis, False)
    pl = facts.played_line
    return WhyLine(pl.ucis, False) if pl is not None and pl.ucis else None


# --- how far the sequence goes -------------------------------------------------------------


def needs_extension(board: chess.Board, ucis: Sequence[str], t: FactThresholds = FACTS) -> bool:
    """The line is too short to show its consequence: it ends in the middle of an exchange,
    its consequence point is followed by fewer than `why_stable_plies` plies (not for mate),
    or there is no consequence yet and it is shorter than the quiet replay + stability."""
    line = _valid(board, ucis)
    if len(line) >= t.consequence_max_plies or _game_over(board, line):
        return False
    c = consequence(board, line, t)
    if c.kind == "mate":
        return False
    if c.kind == "material":
        if not c.settled or c.ply is None:
            return True
        return len(line) - 1 - c.ply < t.why_stable_plies
    return len(line) < t.why_quiet_plies + t.why_stable_plies


def sequence_end(board: chess.Board, ucis: Sequence[str], c: Consequence, t: FactThresholds) -> int:
    """Index of the last step: the consequence point; with no clear consequence,
    `why_quiet_plies` plies, never stopping in the middle of an exchange."""
    if c.ply is not None:
        return c.ply
    if c.kind == "material":  # not settled (line capped): show all of it
        return len(ucis) - 1
    # No clear consequence: about `why_quiet_plies` plies, ending on a quiet position with the
    # material as at the start (never in the middle of an exchange, never looking like a loss
    # that the line wins back later).
    color = board.turn
    start = material.balance(board, color)
    b = board.copy(stack=False)
    even: list[int] = []
    for i, uci in enumerate(ucis):
        b.push_uci(uci)
        if material.balance(b, color) == start and _quiet(b, color, t):
            even.append(i)
    target = min(len(ucis), t.why_quiet_plies) - 1
    before = [i for i in even if i <= target]
    after = [i for i in even if i > target]
    if (before and target - before[-1] <= 2) or not after:
        return before[-1] if before else target
    return after[0]


# --- building the sequence -------------------------------------------------------------------


def build_why(
    facts: MoveFacts,
    kind: Kind,
    ucis: Sequence[str],
    user: chess.Color,
    t: FactThresholds = FACTS,
    *,
    title: str | None = None,
) -> Why:
    """`ucis`: the line from `why_line`, possibly extended (it starts with the first move)."""
    chosen = why_line(facts, kind)
    alternative = chosen is not None and chosen.alternative
    board = chess.Board(facts.fen_before)
    line = _valid(board, ucis)
    c = _relevant(consequence(board, line, t), kind, alternative)
    end = sequence_end(board, line, c, t) if line else -1
    shown = line[: end + 1]
    arrows = _threat_arrows(board, shown)
    mover = board.turn
    defense_side = kind == "refutation" and mover == user

    steps: list[WhyStep] = []
    b = board.copy(stack=False)
    last_capture: int | None = None  # square of the previous step's capture
    for i, uci in enumerate(shown):
        move = chess.Move.from_uci(uci)
        label = _label(b, move)
        created = next((target for start, _, _, _, target in arrows if start == i), None)
        defense = defense_side and i > 0 and b.turn == user
        if i == 0:
            recapture = facts.recapture
        else:
            recapture = last_capture == move.to_square and b.is_capture(move)
        text = _caption(b, move, user, recapture=recapture, threat=created, defense=defense)
        if defense:
            text = "Tu mejor defensa: " + _lower(text)
        if i == 0 and alternative:
            text = "En su lugar, " + _lower(text)
        san = b.san(move)
        color = "white" if b.turn == chess.WHITE else "black"
        last_capture = move.to_square if b.is_capture(move) else None
        b.push(move)
        steps.append(
            WhyStep(
                index=i,
                label=label,
                san=san,
                uci=uci,
                fen=b.fen(),
                color=color,
                caption=text,
                defense=defense,
                consequence=c.ply == i and c.kind != "none",
                arrows=tuple(Arrow(f, to) for start, stop, f, to, _ in arrows if start <= i < stop),
            )
        )

    mt = MarkedText()
    summary = _summary(facts, kind, alternative, c, shown, user, mt)
    text, refs = mt.render(summary)
    first = facts.second_line.sans[0] if alternative and facts.second_line else None
    return Why(
        kind=kind,
        tone="bad" if kind == "refutation" else "good",
        base_ply=facts.ply,
        start_fen=facts.fen_before,
        title=title or _title(facts, kind),
        alternative=first,
        steps=tuple(steps),
        consequence_ply=c.ply if c.kind != "none" and c.ply is not None and c.ply <= end else None,
        summary=text,
        refs=refs,
    )


def _relevant(c: Consequence, kind: Kind, alternative: bool) -> Consequence:
    """The consequence explains the move only if it goes the right way: against the mover in a
    refutation or in the "!" alternative, in its favour in the idea of a good move. Otherwise
    the sequence is treated as having no clear consequence (quiet replay, evaluation summary)."""
    against = kind == "refutation" or alternative
    if c.kind == "mate":
        ok = c.mover_mated == against
    elif c.kind == "material":
        ok = (c.material < 0) == against and c.material != 0
    else:
        return c
    if ok:
        return c
    return Consequence("none", None, 0, (), (), (), (), False, c.settled)


# --- captions ----------------------------------------------------------------------------------


def _caption(
    b: chess.Board,
    move: chess.Move,
    user: chess.Color,
    *,
    recapture: bool,
    threat: int | None,
    defense: bool = False,
) -> str:
    """What one move does, from the facts of the position: mate > capture > check > answer to
    a check > promotion > threat > castling > plain move."""
    me = b.turn
    piece = b.piece_at(move.from_square)
    assert piece is not None
    subject = _own(piece.piece_type, me, user)
    was_check = b.is_check()
    legal = list(b.legal_moves)
    captured = _captured(b, move)
    is_recapture = recapture and b.is_capture(move)
    after = b.copy(stack=False)
    after.push(move)

    parts: list[str] = []
    if captured is not None:
        target = _own(captured, not me, user)
        if was_check and _checker_square(b) == move.to_square:
            parts.append(f"{subject} captura {target} que daba jaque")
        elif is_recapture:
            # After "Tu mejor defensa:" a second colon would read badly.
            what = f"(captura {target})" if defense else f": captura {target}"
            parts.append(f"{subject} recupera{' ' if defense else ''}{what}")
        else:
            parts.append(f"{subject} captura {target}")
    elif was_check:
        if piece.piece_type == chess.KING:
            only_king = all(_piece_type(b, m) == chess.KING for m in legal)
            verb = "tiene que moverse" if only_king else "se aparta del jaque"
            parts.append(f"{subject} {verb}")
        else:
            parts.append(f"{subject} se interpone")
    if move.promotion:
        promoted = es.type_name(_NAMES[move.promotion])
        parts.append(f"corona en {promoted}" if parts else f"{subject} corona en {promoted}")
    if after.is_checkmate():
        parts.append("da jaque mate" if parts else f"{subject} da jaque mate")
    elif after.is_check():
        parts.append("da jaque" if parts else f"{subject} da jaque")
    if not parts:
        if b.is_castling(move):
            parts.append("enrocas" if me == user else "el rival enroca")
        else:
            if threat is not None:
                parts.append(f"{subject} amenaza {_own(threat, not me, user)}")
            else:
                parts.append(f"{subject} va a {chess.square_name(move.to_square)}")
    text = parts[0] + "".join(f" y {p}" for p in parts[1:])
    if len(legal) == 1 and "tiene que" not in text:
        text += " (única jugada)"
    return es.capitalize(text)


def _threat_arrows(board: chess.Board, ucis: Sequence[str]) -> list[tuple[int, int, str, str, int]]:
    """(created at, executed at, from, to, target piece type) for each threat a quiet move
    creates and the same side carries out later in the sequence (a capture on that square)."""
    out: list[tuple[int, int, str, str, int]] = []
    b = board.copy(stack=False)
    boards: list[chess.Board] = []
    for uci in ucis:
        boards.append(b.copy(stack=False))
        b.push_uci(uci)
    for i, uci in enumerate(ucis):
        move = chess.Move.from_uci(uci)
        before = boards[i]
        if before.is_capture(move) or before.is_check():
            continue
        for threat in new_threats(before, move, 1):
            target = chess.parse_square(threat.target.square)
            for j in range(i + 2, len(ucis), 2):
                later = chess.Move.from_uci(ucis[j])
                if later.to_square == target and boards[j].is_capture(later):
                    kind = chess.PIECE_NAMES.index(threat.target.piece)
                    out.append((i, j, threat.attackers[0], threat.target.square, kind))
                    break
    return out


# --- summary -----------------------------------------------------------------------------------


def _summary(
    facts: MoveFacts,
    kind: Kind,
    alternative: bool,
    c: Consequence,
    shown: Sequence[str],
    user: chess.Color,
    mt: MarkedText,
) -> str:
    board = chess.Board(facts.fen_before)
    mover = board.turn
    you = mover == user
    if c.kind == "mate":
        text = _mate_summary(board, shown, c, kind, alternative, you, facts, mt)
    elif c.kind == "material" and c.material != 0:
        text = _material_summary(c, alternative, you, facts, mt)
    else:
        text = _quiet_summary(facts, kind, alternative, you, mt)
    context = _context(facts.win_before, you)
    if context is None:
        return text
    joiner = ", pero " if kind == "refutation" else ": "
    return context + joiner + _lower(text)


def _mate_summary(
    board: chess.Board,
    shown: Sequence[str],
    c: Consequence,
    kind: Kind,
    alternative: bool,
    you: bool,
    facts: MoveFacts,
    mt: MarkedText,
) -> str:
    assert c.ply is not None
    mated_is_mover = c.mover_mated
    moves = (c.ply // 2) + 1 if not mated_is_mover else (c.ply + 1) // 2
    n = "inmediato" if moves == 1 else f"en {moves}"
    if alternative and facts.second_line is not None:
        lead = f"Con {mt.move(facts.second_line, 0)} en su lugar, "
        if mated_is_mover:
            return lead + ("te daban mate " if you else "el rival recibía mate ") + n + "."
        return lead + ("dabas mate " if you else "el rival daba mate ") + n + "."
    if mated_is_mover and kind == "refutation":
        return f"Esta jugada permite mate {n}."
    user_mated = mated_is_mover == you
    if user_mated:
        return f"Te dan mate {n}."
    return f"Das mate {n}." if you else f"El rival da mate {n}."


def _material_summary(
    c: Consequence, alternative: bool, you: bool, facts: MoveFacts, mt: MarkedText
) -> str:
    loses = c.material < 0
    lost, won = (c.lost, c.won) if loses else (c.won, c.lost)
    promoted = c.opponent_promoted if loses else c.promoted
    if not c.settled or not lost:
        # The line ends before the exchanges do, or the material comes from a promotion: only
        # the amount is known for sure.
        what = es.material(abs(c.material))
        if promoted and c.settled:
            who = "el rival corona" if (you == loses) else "coronas"
            what += f" ({who} un peón)"
    else:
        what = es.pieces(lost)
        if won:
            what += f" a cambio de {es.bare(won)}"
        if won or any(p != "pawn" for p in lost):
            what += f" {es.pawns_difference(c.material)}"
    if alternative and facts.second_line is not None:
        verb = (
            ("perderías" if loses else "ganarías")
            if you
            else ("el rival perdería" if loses else "el rival ganaría")
        )
        return f"Con {mt.move(facts.second_line, 0)} en su lugar, {verb} {what}."
    verb = (
        ("Pierdes" if loses else "Ganas")
        if you
        else ("El rival pierde" if loses else "El rival gana")
    )
    text = f"{verb} {what}."
    # A small loss in a ? / ??: the evaluation tells the rest (as in the level-1 text).
    small = abs(c.material) <= 2 and facts.classification in (C.MISTAKE, C.BLUNDER)
    if small and facts.best_line is not None and facts.best_line.sans:
        best = mt.move(facts.best_line, 0)
        compared = _compare(best, facts.win_before, facts.win_after, you)
        if compared is not None:
            text += f" {compared}"
    return text


_STATES = (85.0, 65.0, 55.0, 45.0, 35.0, 15.0)
# Situation of the MOVER (the one whose alternative is compared), past and present: the
# alternative is always theirs ("Con [[g6]] seguías en la partida…").
_PAST = {
    True: (
        "tenías la partida ganada",
        "tenías clara ventaja",
        "estabas algo mejor",
        "mantenías la igualdad",
        "seguías en la partida (el rival algo mejor)",
        "seguías en la partida (el rival con clara ventaja)",
        "la partida ya estaba perdida",
    ),
    False: (
        "el rival tenía la partida ganada",
        "el rival tenía clara ventaja",
        "el rival estaba algo mejor",
        "el rival mantenía la igualdad",
        "el rival seguía en la partida (tú algo mejor)",
        "el rival seguía en la partida (tú con clara ventaja)",
        "el rival ya tenía la partida perdida",
    ),
}
_NOW = {
    True: (
        "sigues con la partida ganada",
        "te queda clara ventaja",
        "quedas algo mejor",
        "hay igualdad",
        "el rival queda algo mejor",
        "el rival queda con clara ventaja",
        "la partida queda perdida",
    ),
    False: (
        "el rival sigue con la partida ganada",
        "al rival le queda clara ventaja",
        "el rival queda algo mejor",
        "hay igualdad",
        "quedas algo mejor",
        "quedas con clara ventaja",
        "el rival tiene la partida perdida",
    ),
}


def _category(mover_win: float) -> int:
    for i, bound in enumerate(_STATES):
        if mover_win > bound or (bound == 45.0 and mover_win >= bound):
            return i
    return len(_STATES)


def _compare(mt_best: str, before_win: float, after_win: float, you: bool) -> str | None:
    """'Con [[g6]] seguías en la partida (el rival algo mejor); ahora la partida queda
    perdida.' None when both evaluations fall in the same category."""
    before, now = _category(before_win), _category(after_win)
    if before == now:
        return None
    return f"Con {mt_best} {_PAST[you][before]}; ahora {_NOW[you][now]}."


def _quiet_summary(
    facts: MoveFacts, kind: Kind, alternative: bool, you: bool, mt: MarkedText
) -> str:
    """No clear consequence: compare evaluations already known (no numbers). Categories are
    from the mover's side: the alternative named is theirs."""
    now = _category(facts.win_after)
    if alternative and facts.second_line is not None:
        other = _category(facts.second_line.win)
        alt = mt.move(facts.second_line, 0)
        played = "tu" if you else "su"
        if other == now:
            worse = "ti" if you else "el rival"
            return (
                f"Con {alt} en su lugar, la posición era peor para {worse}; "
                f"con {played} jugada, {_NOW[you][now]}."
            )
        return f"Con {alt} en su lugar, {_PAST[you][other]}; con {played} jugada, {_NOW[you][now]}."
    if kind == "idea" or facts.best_line is None or not facts.best_line.sans:
        return f"Sin ganancia inmediata de material: tras la jugada, {_NOW[you][now]}."
    best = mt.move(facts.best_line, 0)
    compared = _compare(best, facts.win_before, facts.win_after, you)
    if compared is None:
        return f"{best} era algo más precisa, aunque la valoración no cambia: {_NOW[you][now]}."
    return compared


def _context(mover_win_before: float, you: bool) -> str | None:
    """The position was already decided before the move (SPEC §5.4)."""
    whose = "Tu posición" if you else "La posición del rival"
    if mover_win_before < 100.0 - THRESHOLDS.great_max_win_before:
        return f"{whose} ya estaba perdida"
    if mover_win_before > THRESHOLDS.great_max_win_before:
        return f"{whose} ya estaba ganada"
    return None


_LABELS = {
    C.BLUNDER: "un error grave",
    C.MISTAKE: "un error",
    C.INACCURACY: "una imprecisión",
    C.MISS: "una oportunidad perdida",
}


def _title(facts: MoveFacts, kind: Kind) -> str:
    board = chess.Board(facts.fen_before)
    label = _label(board, chess.Move.from_uci(facts.uci))
    if kind == "idea":
        return f"La idea de {label}"
    what = _LABELS.get(facts.classification)
    return f"Por qué {label} es {what}" if what else f"Por qué {label} no es la mejor"


# --- helpers -----------------------------------------------------------------------------------


def _valid(board: chess.Board, ucis: Sequence[str]) -> tuple[str, ...]:
    b = board.copy(stack=False)
    out: list[str] = []
    for uci in ucis:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in b.legal_moves:
            break
        out.append(uci)
        b.push(move)
    return tuple(out)


def _game_over(board: chess.Board, ucis: Sequence[str]) -> bool:
    b = board.copy(stack=False)
    for uci in ucis:
        b.push_uci(uci)
    return b.is_game_over()


def _quiet(b: chess.Board, color: chess.Color, t: FactThresholds) -> bool:
    return material.resolved_balance(b, color, t.quiescence_max_plies) == material.balance(b, color)


def move_label(fen: str, uci: str) -> str:
    """'21…dxc3' for the move `uci` in position `fen`."""
    return _label(chess.Board(fen), chess.Move.from_uci(uci))


def _label(b: chess.Board, move: chess.Move) -> str:
    number = f"{b.fullmove_number}." if b.turn == chess.WHITE else f"{b.fullmove_number}…"
    return number + b.san(move)


def _own(piece_type: int, color: chess.Color, user: chess.Color) -> str:
    """'tu dama' / 'la dama rival'."""
    name = _NAMES[piece_type]
    noun = es.type_name(name)
    if color == user:
        return f"tu {noun}"
    article = "la" if es.type_feminine(name) else "el"
    return f"{article} {noun} rival"


def _captured(b: chess.Board, move: chess.Move) -> int | None:
    if b.is_en_passant(move):
        return chess.PAWN
    piece = b.piece_at(move.to_square)
    return piece.piece_type if piece is not None and b.is_capture(move) else None


def _checker_square(b: chess.Board) -> int | None:
    checkers = list(b.checkers())
    return checkers[0] if len(checkers) == 1 else None


def _piece_type(b: chess.Board, move: chess.Move) -> int | None:
    piece = b.piece_at(move.from_square)
    return piece.piece_type if piece else None


def _lower(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text
