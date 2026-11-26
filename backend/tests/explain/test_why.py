"""'Ver por qué' (SPEC §5.4): sequences, captions and summaries. Fixed positions, no engine."""

import chess

from app.explain.why import build_why, needs_extension, why_kind, why_line
from tests.explain import scenarios as s

WHITE = chess.WHITE


def test_queen_lost_three_moves_later_replays_until_the_recapture() -> None:
    facts = s.queen_lost_later()
    line = why_line(facts, "refutation")
    assert line is not None
    why = build_why(facts, "refutation", line.ucis, WHITE)
    assert [st.san for st in why.steps] == ["a3", "Re1+", "Kh2", "Nf3+", "Kh3", "Nxh4", "Kxh4"]
    assert why.consequence_ply == 6 and why.steps[-1].consequence
    assert why.title == "Por qué 1.a3 es un error grave"
    assert [st.caption for st in why.steps] == [
        "Tu peón va a a3",
        "La torre rival da jaque",
        "Tu mejor defensa: tu rey tiene que moverse",
        "El caballo rival da jaque",
        "Tu mejor defensa: tu rey tiene que moverse",
        "El caballo rival captura tu dama",
        "Tu mejor defensa: tu rey recupera (captura el caballo rival)",
    ]
    # The user's later moves are the engine's defence, not what was played.
    assert [st.defense for st in why.steps] == [False, False, True, False, True, False, True]
    assert why.summary == ("Pierdes la dama a cambio de caballo (unos 6 peones de diferencia).")
    assert why.tone == "bad"


def test_short_line_needs_extension() -> None:
    board = chess.Board(s.QUEEN_LATER)
    # Stops right after Nxh4: the recapture is pending.
    assert needs_extension(board, s.QUEEN_LATER_LINE[:6])
    # Recapture shown but not yet 4 quiet plies after it.
    assert needs_extension(board, s.QUEEN_LATER_LINE[:7])
    assert not needs_extension(board, s.QUEEN_LATER_LINE)


def test_mate_with_the_piece_and_no_extension() -> None:
    facts = s.fools_mate_g4()
    line = why_line(facts, "refutation")
    assert line is not None
    assert not needs_extension(chess.Board(facts.fen_before), line.ucis)
    why = build_why(facts, "refutation", line.ucis, WHITE)
    assert [st.caption for st in why.steps] == [
        "Tu peón va a g4",
        "La dama rival da jaque mate",
    ]
    assert why.summary == "Esta jugada permite mate inmediato."


def test_opponent_move_is_told_from_the_users_side() -> None:
    facts = s.fools_mate_g4()
    line = why_line(facts, "refutation")
    assert line is not None
    why = build_why(facts, "refutation", line.ucis, chess.BLACK)
    assert why.steps[0].caption == "El peón rival va a g4"
    assert why.steps[1].caption == "Tu dama da jaque mate"
    assert not any(st.defense for st in why.steps)


def test_great_move_replays_the_second_option() -> None:
    facts = s.only_move_nd5()
    assert why_kind(facts.classification) == "idea"
    line = why_line(facts, "idea")
    assert line is not None and line.alternative
    why = build_why(facts, "idea", line.ucis, WHITE)
    assert why.title == "La idea de 1.Nd5"
    assert why.alternative == "Ke2"
    assert why.steps[0].caption == "En su lugar, tu rey va a e2"
    assert why.steps[1].caption == "El peón rival captura tu caballo"
    # The cached line stops after bxc3 (Bxc3 pending): without an extension, no pieces named.
    assert why.summary == ("Con [[Ke2]] en su lugar, perderías material (lo que valen dos peones).")
    assert [r.san for r in why.refs] == ["Ke2"] and why.tone == "good"


def test_no_clear_consequence_compares_evaluations() -> None:
    facts = s.good_a3()
    line = why_line(facts, "refutation")
    assert line is not None
    why = build_why(facts, "refutation", line.ucis, WHITE)
    assert why.consequence_ply is None
    assert why.summary.startswith("[[Nf3]] era algo más precisa") or why.summary.startswith(
        "Con [[Nf3]]"
    )


def test_threat_arrow_until_it_is_carried_out() -> None:
    # Rook lift: Ra4 threatens the h4 bishop along the rank, which falls two plies later.
    board_fen = "6k1/5pp1/8/8/7b/8/5PP1/R5K1 w - - 0 1"
    facts = s.make_facts(
        board_fen,
        "a1a4",
        [s.line("a1a4", "g8f8", "a4h4", cp=300)],
        [s.line("g8f8", "a4h4", cp=-300)],
        s.C.BEST,
    )
    why = build_why(facts, "idea", ("a1a4", "g8f8", "a4h4", "f8e7", "g1h2", "e7e6", "h2g3"), WHITE)
    assert why.steps[0].caption == "Tu torre amenaza el alfil rival"
    assert [len(st.arrows) for st in why.steps[:3]] == [1, 1, 0]
    assert why.steps[2].caption == "Tu torre captura el alfil rival"
    assert why.summary == "Ganas el alfil (unos 3 peones de diferencia)."


def test_position_already_lost_is_said() -> None:
    facts = s.queen_lost_later()
    lost = type(facts)(**{**facts.__dict__, "win_before": 10.0})
    line = why_line(lost, "refutation")
    assert line is not None
    why = build_why(lost, "refutation", line.ucis, WHITE)
    assert why.summary.startswith("Tu posición ya estaba perdida, pero pierdes la dama")


def test_promotion_is_summarised_by_the_amount() -> None:
    # The white pawn promotes: the material comes from the promotion, not from a capture.
    fen = "8/P5k1/8/8/8/8/8/K7 w - - 0 1"
    facts = s.make_facts(
        fen, "a7a8q", [s.line("a7a8q", "g7f6", "a8a1", cp=900)], [s.line("g7f6", cp=-900)], s.C.BEST
    )
    why = build_why(facts, "idea", ("a7a8q", "g7f6", "a1b2", "f6e5", "b2c3", "e5d5"), WHITE)
    assert why.steps[0].caption == "Tu peón corona en dama"
    assert why.summary == "Tu posición ya estaba ganada: ganas mucho material (coronas un peón)."
