"""Les « mots » de Butterfly : types de token et classe ``Token``."""

from dataclasses import dataclass
from enum import Enum, auto

from butterfly.errors import Position


class TypeToken(Enum):
    """Tous les types de token du langage."""

    # Mots-clés
    LET = auto()
    BIND = auto()
    WHEN = auto()
    IF = auto()
    ELSE = auto()
    FOR = auto()
    IN = auto()
    PRINT = auto()
    TRUE = auto()
    FALSE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    # Valeurs et noms
    IDENT = auto()
    INTEGER = auto()
    TEXT = auto()
    # Opérateurs et ponctuation
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ_EQ = auto()
    NOT_EQ = auto()
    LT = auto()
    LT_EQ = auto()
    GT = auto()
    GT_EQ = auto()
    EQ = auto()
    DOT_DOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    SEMICOLON = auto()
    # Divers
    COMMENT = auto()  # produit seulement à la demande (formateur)
    EOF = auto()


KEYWORDS: dict[str, TypeToken] = {
    "let": TypeToken.LET,
    "bind": TypeToken.BIND,
    "when": TypeToken.WHEN,
    "if": TypeToken.IF,
    "else": TypeToken.ELSE,
    "for": TypeToken.FOR,
    "in": TypeToken.IN,
    "print": TypeToken.PRINT,
    "true": TypeToken.TRUE,
    "false": TypeToken.FALSE,
    "and": TypeToken.AND,
    "or": TypeToken.OR,
    "not": TypeToken.NOT,
}

DOUBLE_SYMBOLS: dict[str, TypeToken] = {
    "==": TypeToken.EQ_EQ,
    "!=": TypeToken.NOT_EQ,
    "<=": TypeToken.LT_EQ,
    ">=": TypeToken.GT_EQ,
    "..": TypeToken.DOT_DOT,
}

SINGLE_SYMBOLS: dict[str, TypeToken] = {
    "+": TypeToken.PLUS,
    "-": TypeToken.MINUS,
    "*": TypeToken.STAR,
    "/": TypeToken.SLASH,
    "%": TypeToken.PERCENT,
    "<": TypeToken.LT,
    ">": TypeToken.GT,
    "=": TypeToken.EQ,
    "(": TypeToken.LPAREN,
    ")": TypeToken.RPAREN,
    "{": TypeToken.LBRACE,
    "}": TypeToken.RBRACE,
    ",": TypeToken.COMMA,
    ";": TypeToken.SEMICOLON,
}


@dataclass(frozen=True, slots=True, repr=False)
class Token:
    """Un mot du programme : son type, son texte exact et sa position.

    ``valeur`` contient la valeur déjà décodée d'un ``ENTIER`` (un ``int``) ou
    d'un ``TEXTE`` (le texte sans guillemets, échappements résolus).
    """

    type: TypeToken
    lexeme: str
    position: Position
    value: int | str | None = None

    def __repr__(self) -> str:
        p = self.position
        return f"Token({self.type.name}, {self.lexeme!r}, {p.line}:{p.column})"
