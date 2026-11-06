"""Position dans le source et hiérarchie des erreurs de Butterfly.

Toute erreur du langage hérite de ``ErreurButterfly`` et porte une position.
Son texte suit toujours le même format :

    Erreur sémantique (ligne 3, colonne 1) : 'b' est une cellule dérivée ...

Les erreurs d'exécution n'indiquent que la ligne.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Position:
    """Un endroit du source : ligne et colonne, comptées à partir de 1."""

    line: int
    column: int

    def __str__(self) -> str:
        return f"line {self.line}, column {self.column}"


class ButterflyError(Exception):
    """Classe mère de toutes les erreurs du langage."""

    kind: ClassVar[str] = "Error"

    def __init__(self, message: str, position: Position | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    @property
    def line(self) -> int | None:
        return None if self.position is None else self.position.line

    @property
    def column(self) -> int | None:
        return None if self.position is None else self.position.column

    def __str__(self) -> str:
        if self.position is None:
            return f"{self.kind}: {self.message}"
        return f"{self.kind} ({self.position}): {self.message}"


class LexicalError(ButterflyError):
    """Un caractère ou un texte que le lexer ne sait pas lire."""

    kind = "Lexical error"


class ParseError(ButterflyError):
    """Un programme qui ne respecte pas la grammaire."""

    kind = "Syntax error"


class SemanticError(ButterflyError):
    """Un programme grammaticalement correct, mais qui n'a pas de sens."""

    kind = "Semantic error"


class ExecutionError(ButterflyError):
    """Une erreur qui se produit pendant l'exécution (seule la ligne est connue)."""

    kind = "Runtime error"

    def __init__(self, message: str, line: int) -> None:
        super().__init__(message, Position(line, 0))

    @property
    def column(self) -> int | None:
        return None

    def __str__(self) -> str:
        return f"{self.kind} (line {self.line}): {self.message}"


class CompilationError(Exception):
    """Toutes les erreurs trouvées dans un programme, en une seule fois.

    Le parser et l'analyse sémantique ne s'arrêtent pas à la première erreur :
    ils les collectent, pour que l'utilisateur puisse tout corriger d'un coup.
    """

    def __init__(self, errors: tuple[ButterflyError, ...]) -> None:
        super().__init__(f"{len(errors)} error(s)")
        self.errors = errors

    def __str__(self) -> str:
        return "\n".join(str(error) for error in self.errors)


def context(error: ButterflyError, source: str) -> str:
    """Le message complet, avec la ligne fautive et un repère sous la colonne.

    >>> print(context(ParseError("oops", Position(1, 3)), "ab cd"))
    Syntax error (line 1, column 3): oops
      1 | ab cd
        |   ^
    """
    text = str(error)
    line = error.line
    lines = source.splitlines()
    if line is None or not 1 <= line <= len(lines):
        return text
    number = str(line)
    margin = " " * len(number)
    result = f"{text}\n  {number} | {lines[line - 1]}"
    column = error.column
    if column is not None:
        result += f"\n  {margin} | {' ' * (column - 1)}^"
    return result
