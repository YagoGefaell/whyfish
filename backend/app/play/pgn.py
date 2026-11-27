"""PGN import: parse a PGN and detect which side the user played. Pure."""

import io
from dataclasses import dataclass

import chess
import chess.pgn

from app.play.rules import PlayerColor

VALID_RESULTS = ("1-0", "0-1", "1/2-1/2")


class PgnImportError(ValueError):
    """The PGN cannot be imported. The message is user-facing (Spanish)."""


@dataclass(frozen=True)
class ParsedPgn:
    initial_fen: str
    ucis: list[str]
    headers: dict[str, str]
    games_in_text: int  # only the first one is imported
    # Mover's remaining time after each move (PGN %clk comments), None where missing.
    clocks: tuple[float | None, ...] = ()

    @property
    def white(self) -> str | None:
        return _name(self.headers.get("White"))

    @property
    def black(self) -> str | None:
        return _name(self.headers.get("Black"))

    @property
    def event(self) -> str | None:
        return _name(self.headers.get("Event"))

    @property
    def date(self) -> str | None:
        return _name(self.headers.get("Date"))


def _name(value: str | None) -> str | None:
    """Header value, or None if empty / unknown ("?", "-", "????.??.??")."""
    if value is None or value.strip().strip("?.-") == "":
        return None
    return value.strip()


def parse_pgn(text: str) -> ParsedPgn:
    """First game of `text`, main line only (variations and comments are ignored)."""
    if not text.strip():
        raise PgnImportError("El PGN está vacío.")
    stream = io.StringIO(text)
    first = chess.pgn.read_game(stream)
    if first is None:
        raise PgnImportError("No se encontró ninguna partida en el PGN.")
    count = 1
    while chess.pgn.read_game(stream) is not None:
        count += 1
    if first.errors:
        raise PgnImportError(f"El PGN contiene jugadas no válidas: {first.errors[0]}")
    nodes = list(first.mainline())
    ucis = [node.move.uci() for node in nodes]
    if not ucis:
        raise PgnImportError("El PGN no contiene jugadas.")
    clocks = tuple(node.clock() for node in nodes)
    return ParsedPgn(
        initial_fen=first.board().fen(),
        ucis=ucis,
        headers=dict(first.headers),
        games_in_text=count,
        clocks=clocks if any(c is not None for c in clocks) else (),
    )


def detect_user_color(parsed: ParsedPgn, player_name: str) -> PlayerColor | None:
    """The side whose PGN name matches `player_name` (case-insensitive); None if 0 or 2 match."""
    wanted = player_name.strip().casefold()
    white = (parsed.white or "").casefold() == wanted
    black = (parsed.black or "").casefold() == wanted
    if white and not black:
        return PlayerColor.WHITE
    if black and not white:
        return PlayerColor.BLACK
    return None


def pgn_result(parsed: ParsedPgn, board: chess.Board) -> str:
    """The PGN's result if valid, else the final position's outcome, else "*" (unknown)."""
    result = parsed.headers.get("Result", "*")
    if result in VALID_RESULTS:
        return result
    outcome = board.outcome(claim_draw=True)
    return outcome.result() if outcome else "*"
