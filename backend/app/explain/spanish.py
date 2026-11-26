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


_NUMBERS = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho"}


def pieces(names: tuple[str, ...], definite: bool = True) -> str:
    """'la dama', 'dos peones', 'la torre y un peón', 'un caballo' (definite=False).

    Names are English piece names ("queen", "pawn"...), biggest first. Pawns always take the
    indefinite article ("un peón") or a number ("dos peones").
    """
    groups: list[tuple[str, int]] = []
    for name in names:
        if groups and groups[-1][0] == name:
            groups[-1] = (name, groups[-1][1] + 1)
        else:
            groups.append((name, 1))
    parts: list[str] = []
    for name, count in groups:
        noun, gender = _PIECES[name]
        if count > 1:
            plural = noun.replace("ó", "o") + ("es" if noun.endswith(("n", "l")) else "s")
            parts.append(f"{_NUMBERS.get(count, str(count))} {plural}")
        elif definite and name != "pawn":
            parts.append(f"{'la' if gender == 'f' else 'el'} {noun}")
        else:
            parts.append(f"{'una' if gender == 'f' else 'un'} {noun}")
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " y " + parts[-1]


def exchange(lost: tuple[str, ...], won: tuple[str, ...]) -> str:
    """What one side gives for what: 'la dama a cambio de un caballo', 'un peón'."""
    if not won:
        return pieces(lost)
    return f"{pieces(lost)} a cambio de {pieces(won, definite=False)}"


def more(points: int) -> str:
    """Extra material: 'un peón más', 'dos peones más', 'más material (lo que vale una torre)'."""
    if points <= 1:
        return "un peón más"
    if points == 2:
        return "dos peones más"
    return "más " + material(points)


def bare(names: tuple[str, ...]) -> str:
    """Pieces without articles: 'torre y caballo', 'dos peones', 'torre y peón'."""
    groups: list[tuple[str, int]] = []
    for name in names:
        if groups and groups[-1][0] == name:
            groups[-1] = (name, groups[-1][1] + 1)
        else:
            groups.append((name, 1))
    parts: list[str] = []
    for name, count in groups:
        noun = _PIECES[name][0]
        if count > 1:
            plural = noun.replace("ó", "o") + ("es" if noun.endswith(("n", "l")) else "s")
            parts.append(f"{_NUMBERS.get(count, str(count))} {plural}")
        else:
            parts.append(noun)
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " y " + parts[-1]


def pawns_difference(points: int) -> str:
    """'(un peón de diferencia)', '(unos 4 peones de diferencia)'."""
    n = abs(points)
    return "(un peón de diferencia)" if n == 1 else f"(unos {n} peones de diferencia)"


def type_name(name: str) -> str:
    return _PIECES[name][0]


def type_feminine(name: str) -> bool:
    return _PIECES[name][1] == "f"
