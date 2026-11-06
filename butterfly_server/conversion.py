"""Conversion des objets du langage en réponses JSON pour l'IA."""

from collections.abc import Iterable

from butterfly.errors import ButterflyError, context
from butterfly.semantics import Analysis, SymbolKind
from butterfly.tokens import Token
from butterfly_server.schemas import CellJSON, ErrorJSON, TokenJSON


def error_json(error: ButterflyError, source: str) -> ErrorJSON:
    return {
        "kind": error.kind,
        "message": error.message,
        "line": error.line,
        "column": error.column,
        "context": context(error, source),
    }


def errors_json(errors: Iterable[ButterflyError], source: str) -> list[ErrorJSON]:
    """Une entrée par erreur (une ``ErreurCompilation`` en contient plusieurs)."""
    return [error_json(error, source) for error in errors]


def token_json(token: Token) -> TokenJSON:
    return {
        "type": token.type.name,
        "lexeme": token.lexeme,
        "line": token.position.line,
        "column": token.position.column,
    }


def cells_json(analysis: Analysis) -> list[CellJSON]:
    cells: list[CellJSON] = []
    for name in analysis.cells:
        derived = analysis.kinds[name] is SymbolKind.DERIVED
        cells.append(
            {
                "name": name,
                "kind": "derived" if derived else "source",
                "depends_on": sorted(analysis.dependencies.get(name, ())),
            }
        )
    return cells
