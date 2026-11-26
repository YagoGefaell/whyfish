"""Explanation of one move of a reviewed game: facts -> main idea -> template (SPEC §5).

Templates only (no LLM, CLAUDE.md); the marks and their validation would also serve a possible
future AI.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import chess

from app.analysis.book import OpeningBook
from app.analysis.facts import MoveFacts, build_move_facts
from app.analysis.review import GameReview
from app.analysis.types import Classification, PositionEval
from app.config import FACTS, FactThresholds
from app.explain import spanish as es
from app.explain.idea import Annotation, Idea, arrow, choose_idea, square, valid_annotations
from app.explain.marks import MarkedText, MoveRef
from app.explain.templates import level1, level2

Level = Literal[1, 2]


@dataclass(frozen=True)
class Explanation:
    ply: int
    level: Level
    text: str | None  # None: nothing worth saying (e.g. an obvious best move)
    refs: tuple[MoveRef, ...]  # one per [[mark]], in text order
    annotations: tuple[Annotation, ...]
    idea: str | None
    used: tuple[str, ...]  # facts the text relies on


def facts_for_ply(
    initial_fen: str,
    ucis: Sequence[str],
    evals: Sequence[PositionEval],
    review: GameReview,
    ply: int,
    book: OpeningBook | None,
    t: FactThresholds = FACTS,
) -> MoveFacts:
    """Facts of move `ply` of a game whose review (classifications) is already built."""
    if not 0 <= ply < len(ucis):
        raise IndexError(ply)
    board = chess.Board(initial_fen)
    for uci in ucis[:ply]:
        board.push_uci(uci)
    move = chess.Move.from_uci(ucis[ply])
    reviewed = review.moves[ply]
    after = board.copy()
    after.push(move)
    opening = book.lookup(after) if book else None
    previous = review.moves[ply - 1].classification if ply > 0 else None
    return build_move_facts(
        board,
        move,
        evals[ply],
        evals[ply + 1],
        ply=ply,
        classification=reviewed.classification,
        win_before=reviewed.win_before,
        win_after=reviewed.win_after,
        delta=reviewed.delta,
        opening=opening.name if opening else None,
        after_opponent_error=previous in (Classification.MISTAKE, Classification.BLUNDER),
        t=t,
    )


def explain(facts: MoveFacts, level: Level, you: bool, t: FactThresholds = FACTS) -> Explanation:
    """`you`: the move is the user's (second person) or the opponent's (third person)."""
    idea = choose_idea(facts, t)
    voice = es.Voice(you=you, mover=facts.color)
    mt = MarkedText()
    raw = (level1 if level == 1 else level2)(facts, idea, voice, mt, t)
    text, refs = mt.render(raw) if raw is not None else (None, ())
    return Explanation(
        ply=facts.ply,
        level=level,
        text=text,
        refs=refs,
        annotations=_annotations(facts, idea, level, t) if text else (),
        idea=idea.kind.value if idea and text else None,
        used=idea.used if idea and text else (),
    )


def _annotations(
    facts: MoveFacts, idea: Idea | None, level: Level, t: FactThresholds
) -> tuple[Annotation, ...]:
    if idea is None:
        return ()
    if level == 1:
        return idea.annotations  # already validated and capped at level-1 size
    extra: list[Annotation] = list(idea.annotations)
    extra += [square(h.piece.square, "danger") for h in facts.played.hanging]
    extra += [arrow(th.attackers[0], th.target.square, "attack") for th in facts.played.threats]
    return valid_annotations(extra, facts, t.annotations_level2_max)
