"""Le lexer : transforme le texte source en une suite de tokens.

C'est un **générateur** : il ne lit le source qu'au fur et à mesure qu'on lui
demande des tokens. Une erreur lexicale se produit donc au moment où on arrive
à l'endroit fautif, et les tokens lus avant sont déjà disponibles.
"""

from collections.abc import Iterator

from butterfly.errors import LexicalError, Position
from butterfly.tokens import (
    DOUBLE_SYMBOLS,
    KEYWORDS,
    SINGLE_SYMBOLS,
    Token,
    TypeToken,
)

DIGITS = "0123456789"
ESCAPES = {"n": "\n", '"': '"', "\\": "\\"}


class _Reader:
    """Un curseur dans le source, qui suit la ligne et la colonne."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.i = 0
        self.line = 1
        self.column = 1

    def finished(self) -> bool:
        return self.i >= len(self.source)

    def char(self, offset: int = 0) -> str:
        """Le caractère courant (ou le suivant, etc.) ; ``""`` après la fin."""
        j = self.i + offset
        return self.source[j] if j < len(self.source) else ""

    def advance(self) -> str:
        c = self.source[self.i]
        self.i += 1
        if c == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return c

    def position(self) -> Position:
        return Position(self.line, self.column)


def tokenize(source: str, *, comments: bool = False) -> Iterator[Token]:
    """Produit les tokens de ``source``, terminés par un token ``FIN``.

    Avec ``commentaires=True``, les commentaires sont produits (type
    ``COMMENTAIRE``) au lieu d'être ignorés : le formateur en a besoin.
    """
    reader = _Reader(source)
    while not reader.finished():
        c = reader.char()
        if c in " \t\r\n":
            reader.advance()
            continue
        pos = reader.position()
        if c == "#":
            start = reader.i
            while not reader.finished() and reader.char() != "\n":
                reader.advance()
            if comments:
                yield Token(TypeToken.COMMENT, source[start : reader.i], pos)
        elif c in DIGITS:
            yield _number(reader, pos)
        elif c.isalpha() or c == "_":
            yield _word(reader, pos)
        elif c == '"':
            yield _text(reader, pos)
        elif c + reader.char(1) in DOUBLE_SYMBOLS:
            double_symbol = c + reader.char(1)
            reader.advance()
            reader.advance()
            yield Token(DOUBLE_SYMBOLS[double_symbol], double_symbol, pos)
        elif c in SINGLE_SYMBOLS:
            reader.advance()
            yield Token(SINGLE_SYMBOLS[c], c, pos)
        else:
            raise LexicalError(f"unexpected character {c!r}", pos)
    yield Token(TypeToken.EOF, "", reader.position())


def _number(reader: _Reader, pos: Position) -> Token:
    start = reader.i
    while reader.char() != "" and reader.char() in DIGITS:
        reader.advance()
    # « 1..5 » est une plage ; un point isolé collé à un nombre est une erreur.
    if reader.char() == "." and reader.char(1) != ".":
        raise LexicalError(
            "decimal numbers do not exist: only integers are allowed",
            reader.position(),
        )
    text = reader.source[start : reader.i]
    try:
        value = int(text)
    except ValueError:  # plus de 4300 chiffres : limite de Python
        raise LexicalError("number too large", pos) from None
    return Token(TypeToken.INTEGER, text, pos, value)


def _word(reader: _Reader, pos: Position) -> Token:
    start = reader.i
    while reader.char() != "" and (reader.char().isalnum() or reader.char() == "_"):
        reader.advance()
    text = reader.source[start : reader.i]
    return Token(KEYWORDS.get(text, TypeToken.IDENT), text, pos)


def _text(reader: _Reader, pos: Position) -> Token:
    start = reader.i
    reader.advance()  # le guillemet ouvrant
    pieces: list[str] = []
    while True:
        c = reader.char()
        if c in ("", "\n"):
            raise LexicalError("unclosed text: the closing quote is missing", pos)
        if c == '"':
            reader.advance()
            break
        if c == "\\":
            escape_pos = reader.position()
            reader.advance()
            following = reader.char()
            if following not in ESCAPES:
                raise LexicalError(
                    f"unknown escape '\\{following}' (allowed: \\\" \\\\ \\n)",
                    escape_pos,
                )
            pieces.append(ESCAPES[following])
            reader.advance()
        else:
            pieces.append(reader.advance())
    return Token(TypeToken.TEXT, reader.source[start : reader.i], pos, "".join(pieces))
