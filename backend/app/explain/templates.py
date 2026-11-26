"""Deterministic explanations (provider `none`, SPEC §5.2). Spanish text, English SAN in marks.

Level 1: one or two sentences about the main idea, no evaluation numbers.
Level 2: level 1 + the line commented move by move + the comparison with the best move (or,
for a great move, with the alternative) + a general concept + other facts.
"""

import chess

from app.analysis.detectors.common import PieceOn, require_piece
from app.analysis.detectors.lines import LineOutcome
from app.analysis.detectors.motifs import Motif
from app.analysis.detectors.structure import PawnChange
from app.analysis.detectors.threats import Parried
from app.analysis.facts import MoveEffects, MoveFacts
from app.analysis.types import Classification
from app.config import FACTS, THRESHOLDS, FactThresholds
from app.explain import spanish as es
from app.explain.idea import Idea, IdeaKind, visible_gain, won_piece
from app.explain.marks import MarkedText

C = Classification
K = IdeaKind


def _motif_clause(motif: Motif, tense: str = "present") -> str:
    """'ataca a la vez la dama de d8 y la torre de a8' (present) / 'atacaba…' (past)."""
    past = tense == "past"
    if motif.kind == "fork":
        first, second = motif.targets[0], motif.targets[1]
        verb = "atacaba" if past else "ataca"
        return f"{verb} a la vez {es.the(first)} y {es.the(second)}"
    if motif.kind == "pin":
        pinned, behind = motif.targets
        verb = "clavaba" if past else "clava"
        return f"{verb} {es.the(pinned)} contra {es.the(behind)}"
    if motif.kind == "discovered_attack":
        verb = "descubría" if past else "descubre"
        return f"{verb} un ataque {_of(motif.by)} sobre {es.the(motif.targets[0])}"
    return "daba jaque doble" if past else "da jaque doble"


def _of(piece: PieceOn) -> str:
    """'de la torre de e1' / 'del alfil de b2'."""
    text = es.the(piece)
    return "del" + text[2:] if text.startswith("el ") else "de " + text


def _piece_on(fen: str, square: int) -> PieceOn:
    return require_piece(chess.Board(fen), square)


def _loss(gain: int, piece: PieceOn | None) -> str:
    """The named piece when it explains the gain ('el caballo de c3'), else the amount."""
    return es.the(piece) if piece is not None else es.material(gain)


def _lose(gain: int, piece: PieceOn | None) -> str:
    """'se pierde el caballo de c3' / 'se pierde un peón'."""
    return f"se pierde {es.the(piece)}" if piece is not None else es.lose(gain)


def _fork_loss(motif: Motif, gain: int) -> str | None:
    """What a fork costs: the piece next to the king, or one of the two pieces."""
    if motif.kind != "fork":
        return None
    pieces = [p for p in motif.targets if not p.is_king]
    if len(pieces) < len(motif.targets):
        return es.the(pieces[0]) if pieces else None
    if gain >= min(p.value for p in pieces[:2]) - 2:
        return "una de las dos piezas"
    return None


def _mate_clause(n: int, t: FactThresholds) -> str:
    if n == 1:
        return "mate inmediato"
    if n <= t.mate_spell_max:
        return f"un mate en {n}"
    return "un ataque de mate"


def _best_clause(best: MoveEffects | None, used: tuple[str, ...]) -> str | None:
    """Why the best move was better, from its own facts (positional fallback)."""
    if best is None:
        return None
    if "best.castles" in used:
        return "enrocaba y ponía el rey a salvo"
    if "best.develops" in used:
        return f"desarrollaba {es.a(best.piece)}"
    if "best.threats" in used and best.threats:
        threat = best.threats[0]
        return "amenazaba mate" if threat.kind == "mate" else f"atacaba {es.the(threat.target)}"
    if "best.parried" in used and best.parried:
        return _parried_clause(best.parried[0], past=True)
    return None


def _parried_clause(parried: Parried, past: bool = False) -> str:
    if parried.how == "mate_stopped":
        return "evitaba la amenaza de mate" if past else "evita la amenaza de mate"
    piece = parried.piece_after or parried.threat.target
    threatened = es.agree(piece, "amenazado")
    if parried.how == "moved":
        verb = "ponía a salvo" if past else "pone a salvo"
        return f"{verb} {es.the(parried.threat.target)}, que estaba {threatened}"
    if parried.how == "captured_attacker":
        verb = "eliminaba" if past else "elimina"
        return f"{verb} la pieza que amenazaba {es.the(piece)}"
    verb = "defendía" if past else "defiende"
    return f"{verb} {es.the(piece)}, que estaba {threatened}"


def _negative_clauses(facts: MoveFacts, voice: es.Voice, used: tuple[str, ...]) -> list[str]:
    played = facts.played
    out: list[str] = []
    if "played.weakens_king" in used:
        out.append(f"debilita la protección de {voice.possessive} rey")
    if "played.pawns" in used:
        for change in played.pawns:
            out.extend(_pawn_clause(change, voice))
    return out


def _pawn_clause(change: PawnChange, voice: es.Voice) -> list[str]:
    if change.kind == "doubled":
        return [f"deja un peón doblado en la columna {change.where}"]
    if change.kind == "isolated":
        return [f"deja un peón aislado en la columna {change.where}"]
    if change.kind == "opponent_passed":
        to = "al rival" if voice.you else f"a {es.color_noun(change.color)}"
        return [f"da {to} un peón pasado en {change.where}"]
    return []


# --- level 1 -------------------------------------------------------------------------------


def level1(
    facts: MoveFacts, idea: Idea | None, voice: es.Voice, mt: MarkedText, t: FactThresholds = FACTS
) -> str | None:
    if idea is None:
        return None
    pl, bl, second = facts.played_line, facts.best_line, facts.second_line
    best = mt.move(bl, 0) if bl and bl.sans else None
    better = f" Mejor era {best}." if best and not facts.is_best else ""
    error_prefix = ""
    if facts.after_opponent_error:
        error_prefix = (
            "Tras el error del rival, " if voice.you else f"Tras el error de {voice.opponent}, "
        )

    match idea.kind:
        case K.BOOK:
            return f"Jugada de teoría: {facts.opening}." if facts.opening else "Jugada de teoría."

        case K.ALLOWS_MATE:
            assert pl is not None and pl.mate is not None
            reply = mt.move(pl, 1)
            n = -pl.mate
            clause = _mate_clause(n, t)
            if n == 1:
                text = f"Esta jugada permite {clause}: {reply}."
            else:
                text = f"Esta jugada permite {clause} que empieza con {reply}."
            return text + (f" Había que jugar {best}." if best else "")

        case K.MISSED_MATE:
            assert bl is not None and bl.mate is not None
            n = bl.mate
            if n == 1:
                return es.capitalize(f"{error_prefix}{best} era jaque mate.")
            if n <= t.mate_spell_max:
                return es.capitalize(f"{error_prefix}había un mate en {n} empezando por {best}.")
            return es.capitalize(f"{error_prefix}{best} iniciaba un ataque de mate.")

        case K.HANGING:
            assert pl is not None and idea.piece is not None and idea.index is not None
            piece = idea.piece
            reply = mt.move(pl, idea.index)
            took = (
                f"{reply} {es.pronoun(piece)} captura"
                if idea.index == 1
                else f"acaba cayendo tras {reply}"
            )
            if piece.square == facts.uci[2:4]:
                head = (
                    f"{es.capitalize(es.the(piece, square=False))} queda sin defensa "
                    f"suficiente en {piece.square}"
                )
            else:
                head = voice.say(
                    f"Dejaste {es.the(piece)} sin defensa suficiente",
                    f"{{Subj}} dejaron {es.the(piece)} sin defensa suficiente",
                )
            joiner = ": " if idea.index == 1 else " y "
            return f"{head}{joiner}{took}.{better}"

        case K.TACTIC_ALLOWED:
            assert pl is not None and idea.motif is not None and idea.index is not None
            reply = mt.move(pl, idea.index)
            lead = "Esta jugada permite" if idea.index == 1 else "Tras esta jugada llega"
            fork = _fork_loss(idea.motif, idea.gain)
            lost = f"se pierde {fork}" if fork else _lose(idea.gain, idea.piece)
            return f"{lead} {reply}, que {_motif_clause(idea.motif)}: {lost}.{better}"

        case K.LOSES_MATERIAL:
            assert pl is not None
            reply = mt.move(pl, 1)
            loss = _loss(idea.gain, idea.piece)
            return f"Esta jugada pierde {loss}: la refutación empieza con {reply}.{better}"

        case K.MISSED_GAIN:
            assert best is not None and bl is not None
            if idea.motif is not None:
                won = _fork_loss(idea.motif, idea.gain) or _loss(idea.gain, idea.piece)
                text = f"{error_prefix}{best} {_motif_clause(idea.motif, 'past')} y ganaba {won}."
            elif idea.piece is not None:
                text = f"{error_prefix}{best} ganaba {es.the(idea.piece)}."
            else:
                stop = min((bl.last_mover_capture or 0) + 1, 5)
                follow = " ".join(mt.moves(bl, 1, stop))
                tail = f": sigue {follow}" if follow else ""
                text = f"{error_prefix}{best} ganaba {es.material(idea.gain)}{tail}."
            return es.capitalize(text)

        case K.POSITIONAL:
            negatives = _negative_clauses(facts, voice, idea.used)
            reason = _best_clause(facts.best, idea.used)
            if negatives:
                head = f"Esta jugada {negatives[0]}."
                tail = f" {best} era mejor: {reason}." if reason else better
                return head + tail
            if reason:
                return f"{best} era mejor: {reason}."
            vague = {
                C.INACCURACY: f"No es grave, pero {best} era más precisa.",
                C.MISTAKE: f"{best} era claramente mejor.",
                C.BLUNDER: f"Esta jugada estropea la posición; {best} era mucho mejor.",
                C.MISS: f"{error_prefix}{best} era mucho más fuerte.",
            }
            return es.capitalize(vague.get(facts.classification, f"{best} era mejor."))

        case K.SLIGHTLY_WORSE:
            lead = "Muy buena jugada" if facts.classification == C.EXCELLENT else "Buena jugada"
            if "best_line.material" in idea.used:
                return (
                    f"{lead}, aunque {best} era algo más precisa: ganaba {es.material(idea.gain)}."
                )
            reason = _best_clause(facts.best, idea.used)
            if reason:
                return f"{lead}, aunque {best} era algo más precisa: {reason}."
            return f"{lead}; {best} era algo más precisa."

        case K.MATE:
            assert pl is not None and pl.mate is not None
            me = mt.move(pl, 0)
            if facts.played.is_mate:
                return f"{me} es jaque mate."
            n = pl.mate
            if n <= t.mate_spell_max:
                rest = " ".join(mt.moves(pl, 1, 2 * n - 1))
                return f"{me} fuerza un mate en {n}: sigue {rest}."
            return f"{me} inicia un ataque de mate."

        case K.ONLY_MOVE:
            assert pl is not None and second is not None
            me = mt.move(pl, 0)
            alternative = mt.move(second, 0)
            consequence = _only_move_consequence(pl, second, mt, t)
            if pl.mate is not None and 0 < pl.mate <= t.mate_spell_max:
                rest = " ".join(mt.moves(pl, 1, 2 * pl.mate - 1))
                return (
                    f"{me} fuerza un mate en {pl.mate}: sigue {rest}. "
                    f"Era la única: si {alternative}, {consequence}."
                )
            text = f"{me} era la única buena jugada: si {alternative}, {consequence}."
            if pl.mate is None and visible_gain(pl, t) and facts.material_before >= 0:
                text += f" Además, {me} gana {es.material(pl.material)}."
            return text

        case K.SACRIFICE:
            # Backed by facts.sacrifice: a legal capture with favourable SEE for the opponent,
            # evaluated in the engine line `sacrifice_line` (or bounded by the MultiPV).
            line, sac = facts.sacrifice_line, facts.sacrifice
            assert line is not None and sac is not None and idea.piece is not None
            me = mt.move(line, 0)
            takes = f"{mt.move(line, 1)} {es.pronoun(idea.piece)} captura"
            if sac.bound:
                pl = facts.played_line
                if pl is not None and len(pl.sans) > 1:
                    reply = mt.move(pl, 1)
                    return (
                        f"{me} entrega {es.the(idea.piece)}: si {takes}, al rival le va peor "
                        f"que con su mejor respuesta, {reply}."
                    )
                return (
                    f"{me} entrega {es.the(idea.piece)}, pero "
                    f"tomar{es.pronoun(idea.piece)} no le conviene al rival."
                )
            outcome = _sacrifice_outcome(facts, line, t)
            return f"{me} entrega {es.the(idea.piece)}: si {takes}, {outcome}."

        case K.WINS_MATERIAL:
            assert pl is not None
            me = mt.move(pl, 0)
            if facts.material_before < 0:
                # Behind in material before the move: it wins it back (and maybe more).
                ahead = facts.material_before + idea.gain
                gained = f"recupera {es.material(min(idea.gain, -facts.material_before))}"
                if ahead >= t.material_min:
                    gained = f"recupera el material y gana {es.material(ahead)}"
            elif idea.motif is not None:
                won = _fork_loss(idea.motif, idea.gain) or _loss(idea.gain, idea.piece)
                return f"{me} {_motif_clause(idea.motif)} y gana {won}."
            else:
                captured = facts.played.captured
                if captured is not None and idea.piece == captured:
                    return f"{me} captura {es.the(captured)}, que estaba sin defensa suficiente."
                gained = f"gana {_loss(idea.gain, idea.piece)}"
            stop = min((idea.index or 0) + 1, 4)
            follow = "" if facts.played.captured else " ".join(mt.moves(pl, 1, stop))
            return f"{me} {gained}" + (f": sigue {follow}." if follow else ".")

        case K.THREAT_CREATED:
            me = mt.move(pl, 0) if pl else facts.san
            threats = idea.threats
            check = "da jaque y " if facts.played.gives_check else ""
            if threats[0].kind == "mate":
                return f"{me} {check}amenaza mate."
            first = threats[0]
            attacker = chess.parse_square(first.attackers[0])
            moved_to = chess.parse_square(facts.uci[2:4])
            if attacker != moved_to and chess.Board(facts.fen_after).piece_at(attacker):
                by = _of(_piece_on(facts.fen_after, attacker))
                target = es.the(first.target)
                return f"{me} {check}descubre un ataque {by} sobre {target}."
            if len(threats) >= 2:
                second_target = threats[1].target
                return (
                    f"{me} {check}ataca a la vez {es.the(first.target)} y {es.the(second_target)}."
                )
            weak = ", que no tiene defensa suficiente" if first.gain >= first.target.value else ""
            return f"{me} {check}ataca {es.the(first.target)}{weak}."

        case K.PARRIES:
            assert idea.parried is not None
            me = mt.move(pl, 0) if pl else facts.san
            return f"{me} {_parried_clause(idea.parried)}."
    return None


def _only_move_consequence(
    played: LineOutcome, second: LineOutcome, mt: MarkedText, t: FactThresholds
) -> str:
    reply = mt.move(second, 1) if len(second.sans) > 1 else None
    lead = f"sigue {reply} y " if reply else ""
    if second.mate is not None and second.mate < 0:
        if -second.mate == 1 and reply:
            return f"sigue {reply}, jaque mate"
        return lead + "llega un ataque de mate"
    if second.material <= -t.material_min and played.material - second.material >= t.material_min:
        return lead + _lose(-second.material, won_piece(second, 1, -second.material))
    if visible_gain(played, t) and played.material - second.material >= t.material_min:
        return lead + "la ganancia de material desaparece"
    good, bad = played.win, second.win
    win, lose = THRESHOLDS.winning_above, THRESHOLDS.losing_below
    if good > win and bad < lose:
        return lead + "la posición se da la vuelta"
    if good > win and bad <= win:
        return lead + "la ventaja se esfuma"
    if good > win:
        return lead + "la ventaja se reduce mucho"
    if bad < lose:
        return lead + "la posición queda perdida"
    return lead + "la posición empeora claramente"


def _sacrifice_outcome(facts: MoveFacts, line: LineOutcome, t: FactThresholds) -> str:
    """From the verifying line: its mate / resolved material / evaluation."""
    sac = facts.sacrifice
    assert sac is not None
    if line.mate is not None and line.mate > 0:
        return "llega un ataque de mate"
    if sac.line_end is not None and sac.line_end > 0:
        return "se recupera el material con creces"
    if sac.line_end == 0:
        return "se recupera el material"
    if sac.win >= THRESHOLDS.winning_above:
        return "la posición queda ganadora pese al material de menos"
    if sac.win >= 55:
        return "la posición es buena pese al material de menos"
    return "la posición se mantiene equilibrada pese al material de menos"


# --- level 2 -------------------------------------------------------------------------------

_CONCEPTS: dict[IdeaKind, str] = {
    K.ALLOWS_MATE: "Antes de cada jugada, repasa los jaques y las capturas que tendría el rival.",
    K.MISSED_MATE: "Cuando el rey rival está expuesto, busca primero los jaques: a veces hay mate.",
    K.HANGING: (
        "Antes de mover, comprueba qué piezas quedan sin defensa y qué deja de proteger la "
        "pieza que mueves."
    ),
    K.TACTIC_ALLOWED: (
        "Mira las casillas desde las que una pieza rival atacaría dos cosas a la vez o "
        "clavaría una de tus piezas."
    ),
    K.LOSES_MATERIAL: "Antes de mover, piensa cuál sería la respuesta más fuerte del rival.",
    K.MISSED_GAIN: (
        "En cada jugada busca jaques, capturas y amenazas: a veces el rival deja algo sin defensa."
    ),
    K.POSITIONAL: (
        "Si no hay táctica, compara qué mejora cada candidata: desarrollo, seguridad del rey y "
        "estructura de peones."
    ),
    K.MATE: "Los jaques que dejan al rey sin casillas suelen ser el camino más corto.",
    K.ONLY_MOVE: ("En posiciones tensas, compara varias candidatas: a veces solo una funciona."),
    K.SACRIFICE: "El material no lo es todo: una entrega puede abrir el camino al rey o ganar más.",
    K.WINS_MATERIAL: "Las piezas sin defensa suficiente son el primer objetivo de la táctica.",
    K.THREAT_CREATED: "Una amenaza obliga al rival a responder y te da la iniciativa.",
    K.PARRIES: "Antes de atacar, comprueba si el rival amenaza algo.",
}


def _comment(line: LineOutcome, index: int, facts_board_fen: str) -> str:
    """Short comment for one ply of a line: capture, check, mate, promotion."""
    board = chess.Board(facts_board_fen)
    for uci in line.ucis[:index]:
        board.push_uci(uci)
    move = chess.Move.from_uci(line.ucis[index])
    parts: list[str] = []
    capture = next((c for c in line.captures if c.index == index), None)
    if capture is not None:
        parts.append(f"captura {es.the(capture.captured)}")
    if move.promotion:
        parts.append("corona")
    if board.is_castling(move):
        parts.append("enroca")
    board.push(move)
    if board.is_checkmate():
        parts.append("jaque mate")
    elif board.is_check():
        parts.append("jaque")
    return ", ".join(parts)


def commented_line(
    line: LineOutcome, start: int, plies: int, fen: str, mt: MarkedText
) -> str | None:
    items: list[str] = []
    for index in range(start, min(start + plies, len(line.sans))):
        mark = mt.move(line, index)
        comment = _comment(line, index, fen)
        items.append(f"{mark} ({comment})" if comment else mark)
    return ", ".join(items) + "." if items else None


def _outcome(line: LineOutcome, t: FactThresholds) -> str:
    if line.mate is not None:
        return "se da mate" if line.mate > 0 else "se recibe mate"
    if line.material >= t.material_min:
        return es.win(line.material)
    if line.material <= -t.material_min:
        return es.lose(-line.material)
    return "el material se mantiene"


def level2(
    facts: MoveFacts, idea: Idea | None, voice: es.Voice, mt: MarkedText, t: FactThresholds = FACTS
) -> str | None:
    first = level1(facts, idea, voice, mt, t)
    if first is None:
        return None
    paragraphs = [first]
    pl, bl, second = facts.played_line, facts.best_line, facts.second_line
    fen = facts.fen_before
    is_error = facts.classification in (C.INACCURACY, C.MISTAKE, C.BLUNDER, C.MISS)

    if pl is not None and len(pl.sans) > 1 and idea is not None and idea.kind != K.BOOK:
        start = 1 if is_error or facts.classification in (C.EXCELLENT, C.GOOD) else 0
        text = commented_line(pl, start, t.commented_line_plies, fen, mt)
        if text:
            title = "Lo que pasa tras la jugada" if start == 1 else "La idea"
            paragraphs.append(f"{title}: {text}")

    if bl is not None and not facts.is_best and idea is not None and idea.kind != K.BOOK:
        text = commented_line(bl, 0, t.commented_line_plies, fen, mt)
        if text and pl is not None:
            paragraphs.append(
                f"Con la mejor: {text} La diferencia: con {mt.move(bl, 0)} {_outcome(bl, t)}; "
                f"con la jugada hecha, {_outcome(pl, t)}."
            )

    if second is not None and idea is not None and idea.kind == K.ONLY_MOVE:
        text = commented_line(second, 0, t.commented_line_plies, fen, mt)
        if text:
            paragraphs.append(f"La alternativa: {text}")

    if idea is not None and idea.kind in _CONCEPTS:
        paragraphs.append(_CONCEPTS[idea.kind])

    extra = _extra_facts(facts, idea, voice)
    if extra:
        paragraphs.append("Además: " + " ".join(extra))
    return "\n\n".join(paragraphs)


def _extra_facts(facts: MoveFacts, idea: Idea | None, voice: es.Voice) -> list[str]:
    """Secondary facts not already used by the main idea (at most three sentences)."""
    used = set(idea.used) if idea else set()
    out: list[str] = []
    played = facts.played
    if "played.hanging" not in used:
        for hanging in played.hanging[1:] if idea and idea.kind == K.HANGING else played.hanging:
            if facts.classification in (C.BRILLIANT,):
                break
            out.append(f"{es.capitalize(es.the(hanging.piece))} queda sin defensa suficiente.")
    if "played.weakens_king" not in used and played.weakens_king:
        out.append(f"La jugada debilita la protección de {voice.possessive} rey.")
    if "played.pawns" not in used:
        for change in played.pawns:
            out.extend(es.capitalize(c) + "." for c in _pawn_clause(change, voice))
            if change.kind == "passed":
                out.append(f"Consigue un peón pasado en {change.where}.")
    if played.develops and facts.classification not in (C.BOOK,):
        out.append(f"Desarrolla {es.a(played.piece)}.")
    if played.castles:
        out.append("Pone el rey a salvo con el enroque.")
    return out[:3]
