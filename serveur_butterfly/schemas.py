"""Les formes des réponses des outils MCP.

Ce sont des ``TypedDict`` : le SDK en déduit le **schéma de sortie** de chaque
outil, que l'IA lit avant d'appeler l'outil. Pas de
``from __future__ import annotations`` ici : le SDK inspecte les annotations à
l'exécution pour construire les schémas.
"""

from typing import Any, Literal, TypedDict


class ErreurJSON(TypedDict):
    genre: str  # "Erreur de syntaxe", "Erreur sémantique", ...
    message: str
    ligne: int | None
    colonne: int | None  # None pour une erreur d'exécution
    contexte: str  # le message complet, avec la ligne fautive et un repère


class TokenJSON(TypedDict):
    type: str
    lexeme: str
    ligne: int
    colonne: int


class ResultatTokenize(TypedDict):
    ok: bool
    tokens: list[TokenJSON]  # en cas d'erreur lexicale : ceux lus avant l'erreur
    erreurs: list[ErreurJSON]


class ResultatParse(TypedDict):
    ok: bool
    arbre: dict[str, Any] | None  # chaque nœud a une clé "type"
    erreurs: list[ErreurJSON]


class CelluleJSON(TypedDict):
    nom: str
    genre: Literal["source", "derivee"]
    depend_de: list[str]  # pour une cellule dérivée : les cellules de sa formule


class ResultatCheck(TypedDict):
    ok: bool
    erreurs: list[ErreurJSON]
    cellules: list[CelluleJSON]  # les cellules du niveau supérieur, si ok


class ResultatTranspile(TypedDict):
    ok: bool
    python: str | None
    erreurs: list[ErreurJSON]


class ResultatFormat(TypedDict):
    ok: bool
    source: str | None
    erreurs: list[ErreurJSON]


Statut = Literal[
    "ok",
    "erreur_compilation",
    "erreur_execution",
    "delai_depasse",
    "sortie_tronquee",
    "memoire_depassee",
    "erreur_interne",
]


class ResultatRun(TypedDict):
    statut: Statut
    sortie: str  # ce que le programme a affiché (même en cas d'erreur)
    erreurs: list[ErreurJSON]
    duree_secondes: float
