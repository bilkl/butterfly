"""Les formes des réponses des outils MCP.

Ce sont des ``TypedDict`` : le SDK en déduit le **schéma de sortie** de chaque
outil, que l'IA lit avant d'appeler l'outil. Pas de
``from __future__ import annotations`` ici : le SDK inspecte les annotations à
l'exécution pour construire les schémas.
"""

from typing import Any, Literal, TypedDict


class ErrorJSON(TypedDict):
    kind: str  # "Erreur de syntaxe", "Erreur sémantique", ...
    message: str
    line: int | None
    column: int | None  # None pour une erreur d'exécution
    context: str  # le message complet, avec la ligne fautive et un repère


class TokenJSON(TypedDict):
    type: str
    lexeme: str
    line: int
    column: int


class TokenizeResult(TypedDict):
    ok: bool
    tokens: list[TokenJSON]  # en cas d'erreur lexicale : ceux lus avant l'erreur
    errors: list[ErrorJSON]


class ParseResult(TypedDict):
    ok: bool
    tree: dict[str, Any] | None  # chaque nœud a une clé "type"
    errors: list[ErrorJSON]


class CellJSON(TypedDict):
    name: str
    kind: Literal["source", "derived"]
    depends_on: list[str]  # pour une cellule dérivée : les cellules de sa formule


class CheckResult(TypedDict):
    ok: bool
    errors: list[ErrorJSON]
    cells: list[CellJSON]  # les cellules du niveau supérieur, si ok


class TranspileResult(TypedDict):
    ok: bool
    python: str | None
    errors: list[ErrorJSON]


class FormatResult(TypedDict):
    ok: bool
    source: str | None
    errors: list[ErrorJSON]


Status = Literal[
    "ok",
    "compilation_error",
    "execution_error",
    "timeout",
    "output_truncated",
    "memory_exceeded",
    "internal_error",
]


class RunResult(TypedDict):
    status: Status
    output: str  # ce que le programme a affiché (même en cas d'erreur)
    errors: list[ErrorJSON]
    duration_seconds: float
