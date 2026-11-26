from collections.abc import Callable
from typing import Literal

import pytest

from app.analysis.facts import MoveFacts
from app.explain.marks import extract_marks, invalid_marks
from app.explain.service import explain
from tests.explain import scenarios as s

LEVEL1 = {
    s.fools_mate_g4: "Esta jugada permite mate inmediato: [[Qh4#]]. Había que jugar [[e3]].",
    s.queen_to_g5: (
        "La dama queda sin defensa suficiente en g5: [[Nxg5]] la captura. Mejor era [[Nc6]]."
    ),
    s.knight_left_hanging: (
        "Dejaste el caballo de c3 sin defensa suficiente: [[bxc3]] lo captura. Mejor era [[Nd5]]."
    ),
    s.only_move_nd5: (
        "[[Nd5]] era la única buena jugada: si [[Ke2]], sigue [[bxc3]] y se pierde el caballo "
        "de c3."
    ),
    s.allows_fork: (
        "Esta jugada permite [[Nc7+]], que ataca a la vez el rey y la torre de a8: se pierde la "
        "torre de a8. Mejor era [[Rb8]]."
    ),
    s.missed_knight: "[[Qxd5]] ganaba el caballo de d5.",
    s.takes_knight: "[[Qxd5]] captura el caballo de d5, que estaba sin defensa suficiente.",
    s.book_e4: "Jugada de teoría: King's Pawn Game.",
    s.good_a3: "Buena jugada, aunque [[Nf3]] era algo más precisa: desarrollaba un caballo.",
    s.knight_sacrifice: (
        "[[Nf5]] entrega el caballo de f5: si [[gxf5]] lo captura, la posición se mantiene "
        "equilibrada pese al material de menos."
    ),
    s.declined_knight_sacrifice: (
        "[[Nf5]] entrega el caballo de f5: si [[gxf5]] lo captura, al rival le va peor que con "
        "su mejor respuesta, [[Kh8]]."
    ),
}


@pytest.mark.parametrize("level", [1, 2])
def test_no_sacrifice_wording_without_a_resolved_sacrifice(level: Literal[1, 2]) -> None:
    """Even with a (wrong) !! label, the text cannot claim a sacrifice the facts do not show."""
    facts = s.forced_loss_labelled_brilliant()
    assert facts.sacrifice is None
    text = (explain(facts, level, you=True).text or "").lower()
    for word in ("entrega", "sacrific", "material de menos"):
        assert word not in text


@pytest.mark.parametrize("scenario", list(LEVEL1), ids=lambda f: f.__name__)
def test_level1_text(scenario: Callable[[], MoveFacts]) -> None:
    assert explain(scenario(), 1, you=True).text == LEVEL1[scenario]


def test_third_person_for_the_opponent() -> None:
    text = explain(s.fools_mate_missed(), 1, you=False).text
    assert text == "Tras el error de las blancas, [[Qh4#]] era jaque mate."
    text = explain(s.knight_left_hanging(), 1, you=False).text
    assert text is not None and text.startswith("Las blancas dejaron el caballo de c3")


def test_obvious_recapture_has_no_explanation() -> None:
    e = explain(s.recapture(), 1, you=True)
    assert (e.text, e.refs, e.annotations, e.idea) == (None, (), (), None)


def test_refs_point_to_the_line_of_each_mark() -> None:
    e = explain(s.queen_to_g5(), 1, you=True)
    # Both lines start at the position before the move (ply 0 of this FEN-only game).
    assert [(r.san, r.line, r.base_ply, r.path) for r in e.refs] == [
        ("Nxg5", "played", 0, ("d8g5", "f3g5")),
        ("Nc6", "best", 0, ("b8c6",)),
    ]


def test_annotations_show_the_main_idea() -> None:
    e = explain(s.queen_to_g5(), 1, you=True)
    assert [(a.kind, a.role, a.square, a.from_square, a.to_square) for a in e.annotations] == [
        ("square", "danger", "g5", None, None),
        ("arrow", "threat", None, "f3", "g5"),
    ]
    fork = explain(s.allows_fork(), 1, you=True)
    assert ("arrow", "threat", "b5", "c7") in [
        (a.kind, a.role, a.from_square, a.to_square) for a in fork.annotations
    ]


@pytest.mark.parametrize("scenario", s.ALL, ids=lambda f: f.__name__)
@pytest.mark.parametrize("level", [1, 2])
def test_marks_are_valid_and_referenced(scenario: Callable[[], MoveFacts], level: int) -> None:
    facts = scenario()
    e = explain(facts, 1 if level == 1 else 2, you=True)
    if e.text is None:
        return
    marks = extract_marks(e.text)
    assert invalid_marks(e.text, facts) == []
    assert [r.san for r in e.refs] == marks
    assert len(e.annotations) <= (3 if level == 1 else 6)
    assert "\x00" not in e.text
    # No evaluation numbers in level 1.
    if level == 1:
        assert "%" not in e.text and "+0" not in e.text


def test_level2_adds_lines_and_a_concept() -> None:
    text = explain(s.knight_left_hanging(), 2, you=True).text
    assert text is not None
    paragraphs = text.split("\n\n")
    assert paragraphs[0] == LEVEL1[s.knight_left_hanging]
    assert paragraphs[1].startswith("Lo que pasa tras la jugada: [[bxc3]] (captura el caballo")
    assert paragraphs[2].startswith("Con la mejor: [[Nd5]]")
    assert "comprueba qué piezas quedan sin defensa" in paragraphs[3]


def test_invented_move_is_detected() -> None:
    facts = s.queen_to_g5()
    assert invalid_marks("Mejor era [[Nc6]], no [[Qh5]].", facts) == ["Qh5"]
