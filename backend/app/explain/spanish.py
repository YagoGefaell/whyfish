"""Spanish wording for pieces, material and players. Moves stay in English SAN (CLAUDE.md)."""

from dataclasses import dataclass

from app.analysis.detectors.common import PieceOn

# name, gender (m/f)
_PIECES: dict[str, tuple[str, str]] = {
    "pawn": ("peón", "m"),
    "knight": ("caballo", "m"),
    "bishop": ("alfil", "m"),
    "rook": ("torre", "f"),
    "queen": ("dama", "f"),
    "king": ("rey", "m"),
}


def piece_name(piece: PieceOn) -> str:
    return _PIECES[piece.piece][0]


def feminine(piece: PieceOn) -> bool:
    return _PIECES[piece.piece][1] == "f"


def the(piece: PieceOn, square: bool = True) -> str:
    """'el caballo de f3', 'la torre de a1', 'el rey'."""
    article = "la" if feminine(piece) else "el"
    if piece.is_king or not square:
        return f"{article} {piece_name(piece)}"
    return f"{article} {piece_name(piece)} de {piece.square}"


def a(piece: PieceOn) -> str:
    """'un caballo', 'una torre'."""
    return f"{'una' if feminine(piece) else 'un'} {piece_name(piece)}"


def pronoun(piece: PieceOn) -> str:
    """Direct object pronoun: 'lo' / 'la'."""
    return "la" if feminine(piece) else "lo"


def agree(piece: PieceOn, masculine: str) -> str:
    """Adjective agreement: agree(rook, 'amenazado') -> 'amenazada'."""
    if feminine(piece) and masculine.endswith("o"):
        return masculine[:-1] + "a"
    return masculine


def material(points: int) -> str:
    """Material in words, without naming a specific piece."""
    if points <= 1:
        return "un peón"
    if points == 2:
        return "material (lo que valen dos peones)"
    if points <= 4:
        return "material (lo que vale una pieza)"
    if points <= 6:
        return "material (lo que vale una torre)"
    return "mucho material"


def lose(points: int) -> str:
    """'se pierde un peón'."""
    return f"se pierde {material(points)}"


def win(points: int) -> str:
    """'se gana un peón'."""
    return f"se gana {material(points)}"


def color_noun(color: str) -> str:
    return "las blancas" if color == "white" else "las negras"


def capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


@dataclass(frozen=True)
class Voice:
    """Second person for the user's moves, third person (by colour) for the opponent's."""

    you: bool
    mover: str  # "white" | "black"

    @property
    def subject(self) -> str:
        """'Las blancas' (only used in the third person)."""
        return capitalize(color_noun(self.mover))

    @property
    def possessive(self) -> str:
        return "tu" if self.you else "su"

    @property
    def opponent(self) -> str:
        """'el rival' / 'las negras'."""
        return "el rival" if self.you else color_noun("black" if self.mover == "white" else "white")

    def say(self, you: str, they: str) -> str:
        return you if self.you else they.replace("{Subj}", self.subject)
