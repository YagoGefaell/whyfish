"""Serializable references to pieces and squares shared by the detectors."""

from dataclasses import dataclass

import chess

from app.analysis.material import PIECE_VALUES

PIECE_NAMES: dict[chess.PieceType, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}
PIECE_TYPES: dict[str, chess.PieceType] = {name: kind for kind, name in PIECE_NAMES.items()}


def color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


@dataclass(frozen=True)
class PieceOn:
    """A piece on a square, e.g. PieceOn("knight", "white", "f3")."""

    piece: str
    color: str
    square: str

    @property
    def value(self) -> int:
        return PIECE_VALUES[PIECE_TYPES[self.piece]]

    @property
    def is_king(self) -> bool:
        return self.piece == "king"


def piece_on(board: chess.Board, square: chess.Square) -> PieceOn | None:
    piece = board.piece_at(square)
    if piece is None:
        return None
    return PieceOn(
        PIECE_NAMES[piece.piece_type], color_name(piece.color), chess.square_name(square)
    )


def require_piece(board: chess.Board, square: chess.Square) -> PieceOn:
    found = piece_on(board, square)
    if found is None:
        raise ValueError(f"no piece on {chess.square_name(square)}")
    return found


def by_value(board: chess.Board, squares: chess.SquareSet) -> tuple[str, ...]:
    """Square names ordered by the value of the piece on them (least valuable first)."""

    def key(square: chess.Square) -> tuple[int, int]:
        piece = board.piece_at(square)
        value = PIECE_VALUES[piece.piece_type] if piece else 0
        return (value or 100, square)  # the king last

    return tuple(chess.square_name(s) for s in sorted(squares, key=key))


def as_side_to_move(board: chess.Board, color: chess.Color) -> chess.Board:
    """Copy of `board` with `color` to move ("if the other side passed"). En passant is cleared."""
    b = board.copy(stack=False)
    if b.turn != color:
        b.turn = color
        b.ep_square = None
    return b
